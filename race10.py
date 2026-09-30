"""Race the single agent against the kitchen squad on the same 10 Week-6 cases.

Resumable: each finished run is written to race10_results.json at once, and a spent
daily quota stops the runner instead of burning retries. --report makes no API call.

    python race10.py --arm both --key 1 --pace 20
    python race10.py --inject allergen --case s12 --key 2      # the failure run
    python race10.py --report                                   # table, multiplier, log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_agent import DEFAULT_CONFIG, load_config, run_agent
from orchestrator import run_squad
from recipe_rag import is_rate_limit_error

PROJECT_DIR = Path(__file__).parent
CASES_FILE = PROJECT_DIR / "race10_cases.json"
RESULTS_FILE = PROJECT_DIR / "race10_results.json"
VERDICTS_FILE = PROJECT_DIR / "race10_verdicts.json"
HANDOFF_LOG = PROJECT_DIR / "handoffs.log"
ARMS = ("single", "squad")


def load_cases() -> list[dict[str, Any]]:
    """The 10 Week-6 cases, fixed before any run."""
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def load_results() -> dict[str, Any]:
    """Every stored run, keyed arm:case_id."""
    if not RESULTS_FILE.exists():
        return {}
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


def save_results(results: dict[str, Any]) -> None:
    """Write all runs, so an interruption loses at most the run in flight."""
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")


def is_quota_error(error: BaseException) -> bool:
    """A rate-limit refusal, even when anyio wraps it in nested exception groups."""
    if isinstance(error, BaseExceptionGroup):
        return any(is_quota_error(inner) for inner in error.exceptions)
    return is_rate_limit_error(error) or (
        error.__cause__ is not None and is_quota_error(error.__cause__))


def use_key(slot: int) -> None:
    """Point the SDK at one project's key. The value is never printed."""
    name = "GEMINI_API_KEY" if slot == 1 else f"GEMINI_API_KEY{slot}"
    os.environ["GEMINI_API_KEY"] = os.environ[name]


async def run_one(arm: str, request: str, faults: dict[str, int]) -> dict[str, Any]:
    """One request through one arm, normalised to the same record shape."""
    config = load_config(DEFAULT_CONFIG)
    if arm == "squad":
        return await run_squad(request, config, faults=faults)
    result = await run_agent(request, config)
    return {
        "arm": "single",
        "request": request,
        "answer": result["answer"],
        "evidence": result["calls"],
        "handoffs": [{
            "handoff": f"user -> single agent ({result['laps']} laps)", "status": result["stop_reason"],
            "payload_chars": len(request), "model_calls": result["laps"],
            "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
        }],
        "model_calls": result["laps"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "total_tokens": result["total_tokens"],
        "cost_usd": result["cost_usd"],
        "latency_seconds": result["latency_seconds"],
    }


def race(arms: list[str], key: int, pace: float, faults: dict[str, int], only: str | None) -> None:
    """Run every missing arm:case, pacing between runs, stopping on a spent quota."""
    use_key(key)
    results = load_results()
    prefix = "squad_fault" if faults else None
    for case in load_cases():
        if only and case["case_id"] != only:
            continue
        for arm in arms:
            slot = f"{prefix or arm}:{case['case_id']}"
            if slot in results:
                continue
            print(f"{slot}: {case['request']}")
            try:
                record = asyncio.run(run_one(arm, case["request"], faults))
            except Exception as error:
                if is_quota_error(error):
                    print(f"  quota refused on key {key}; stopping. Resume with another --key.")
                    return
                raise
            record.update({"case_id": case["case_id"], "key_slot": key, "faults": faults,
                           "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            results[slot] = record
            save_results(results)
            print(f"  {record['model_calls']} calls, {record['total_tokens']} tokens, "
                  f"{record['latency_seconds']}s")
            time.sleep(pace)


def nearest_rank(values: list[float], percentile: float) -> float:
    """Nearest-rank percentile. With n=10, p99 is the slowest run."""
    ordered = sorted(values)
    return ordered[max(1, math.ceil(percentile / 100 * len(ordered))) - 1]


def report() -> None:
    """The four numbers per arm, the multiplier, the dominant hand-off, and handoffs.log."""
    cases = [case["case_id"] for case in load_cases()]
    results = load_results()
    verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8")) if VERDICTS_FILE.exists() else {}
    by_run = verdicts.get("by_run", {})
    missing = [f"{arm}:{cid}" for arm in ARMS for cid in cases if f"{arm}:{cid}" not in results]
    if missing:
        print(f"INTERIM - missing runs: {', '.join(missing)}")
        # Only cases both arms finished, so the two columns always cover the same questions.
        cases = [cid for cid in cases if all(f"{arm}:{cid}" in results for arm in ARMS)]
        print(f"comparing the {len(cases)} cases both arms finished: {', '.join(cases)}\n")

    rows: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        runs = [results[f"{arm}:{cid}"] for cid in cases if f"{arm}:{cid}" in results]
        if not runs:
            continue
        judged = [by_run.get(f"{arm}:{cid}", {}).get("verdict") for cid in cases]
        passes = sum(1 for v in judged if v == "PASS")
        latencies = [run["latency_seconds"] for run in runs]
        rows[arm] = {
            "runs": len(runs),
            "pass": f"{passes}/{len(cases)}" if by_run else "not judged",
            "p50": nearest_rank(latencies, 50),
            "p99": nearest_rank(latencies, 99),
            "tokens": sum(run["total_tokens"] for run in runs),
            "calls": sum(run["model_calls"] for run in runs),
            "cost": sum(run["cost_usd"] for run in runs) / len(runs),
        }
    print("| metric | single agent | squad |")
    print("|---|---|---|")
    for key, label, fmt in [("pass", "pass rate (judge_v2)", "{}"), ("p50", "p50 latency (s)", "{:.1f}"),
                            ("p99", "p99 latency (s)", "{:.1f}"), ("tokens", "total tokens", "{:,}"),
                            ("cost", "cost per question (USD)", "{:.5f}"), ("calls", "model calls", "{}")]:
        cells = [fmt.format(rows[arm][key]) if arm in rows else "-" for arm in ARMS]
        print(f"| {label} | {cells[0]} | {cells[1]} |")

    if "single" in rows and "squad" in rows:
        multiplier = rows["squad"]["tokens"] / rows["single"]["tokens"]
        shares: dict[str, int] = defaultdict(int)
        for cid in cases:
            for handoff in results.get(f"squad:{cid}", {}).get("handoffs", []):
                shares[handoff["handoff"]] += handoff["total_tokens"]
        total = sum(shares.values())
        print(f"\ncontext re-send multiplier: {rows['squad']['tokens']:,} / "
              f"{rows['single']['tokens']:,} = {multiplier:.1f}x")
        for handoff, tokens in sorted(shares.items(), key=lambda item: -item[1]):
            print(f"  {handoff:<42} {tokens:>7,} tokens  {tokens / total:5.1%}")

    lines = ["# arm\tcase\thandoff\tstatus\tpayload_chars\tmodel_calls\tinput_tokens\t"
             "output_tokens\ttotal_tokens"]
    for slot in sorted(results):
        run = results[slot]
        for h in run["handoffs"]:
            lines.append(f"{slot.split(':')[0]}\t{run['case_id']}\t{h['handoff']}\t{h['status']}\t"
                         f"{h['payload_chars']}\t{h['model_calls']}\t{h['input_tokens']}\t"
                         f"{h['output_tokens']}\t{h['total_tokens']}")
    HANDOFF_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{HANDOFF_LOG.name}: {len(lines) - 1} hand-offs")


def main() -> None:
    """Race, inject a failure, or report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=[*ARMS, "both"], default="both")
    parser.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot to use")
    parser.add_argument("--pace", type=float, default=20.0, help="seconds between runs")
    parser.add_argument("--inject", choices=["allergen", "substitution"],
                        help="make this worker return HTTP 500 (squad only)")
    parser.add_argument("--case", help="run only this case_id")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        report()
        return
    if args.inject:
        if not args.case:
            parser.error("--inject needs --case")
        race(["squad"], args.key, args.pace, {args.inject: 500}, args.case)
        return
    arms = list(ARMS) if args.arm == "both" else [args.arm]
    race(arms, args.key, args.pace, {}, args.case)


if __name__ == "__main__":
    main()
