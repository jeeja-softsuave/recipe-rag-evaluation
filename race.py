"""Race the agent against the fixed workflow over the same 10 requests.

Resumable: every completed run is written to race_results.json immediately, so a spent
quota costs nothing but time. Run with --system to do one side at a time.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any

from agent import run_agent
from recipe_rag import is_rate_limit_error
from tools import call_tool
from workflow import run_workflow

REQUESTS_FILE = Path(__file__).parent / "requests.jsonl"
RESULTS_FILE = Path(__file__).parent / "race_results.json"
CSV_FILE = Path(__file__).parent / "race.csv"
SYSTEMS = {"agent": run_agent, "workflow": run_workflow}
# The free-tier limit is 20 requests per DAY per project, not per minute: 180s of idle
# never cleared it. Pacing only avoids wasting retries against an already-spent allowance.
PACE_SECONDS = 45.0


def load_requests() -> list[dict[str, Any]]:
    """Load the 10 race requests."""
    lines = REQUESTS_FILE.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_results() -> dict[str, Any]:
    """Load whatever runs already exist."""
    if not RESULTS_FILE.exists():
        return {}
    return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))


def _norm(text: Any) -> str:
    """Normalise an ingredient name so casing and spacing do not decide a pass."""
    return " ".join(str(text).strip().lower().split())


def _chain(pairs: Any) -> list[tuple[str, str]]:
    """Normalise a substitution chain to comparable pairs."""
    out = []
    for pair in pairs or []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            out.append((_norm(pair[0]), _norm(pair[1])))
        elif isinstance(pair, dict):
            out.append((_norm(pair.get("from")), _norm(pair.get("to"))))
    return out


def score(request: dict[str, Any], output: dict[str, Any] | None) -> dict[str, Any]:
    """Score one run against the answer key, reporting which part failed."""
    if not output:
        return {"passed": False, "why": "no parseable output"}

    failures = []
    if output.get("recipe_id") != request["expect_recipe_id"]:
        failures.append(f"recipe_id={output.get('recipe_id')}")
    if output.get("target_servings") != request["expect_target_servings"]:
        failures.append(f"target_servings={output.get('target_servings')}")
    if _chain(output.get("substitutions")) != _chain(request["expect_substitutions"]):
        failures.append(f"substitutions={_chain(output.get('substitutions'))}")
    if bool(output.get("no_safe_substitute")) != request["expect_no_safe_substitute"]:
        failures.append(f"no_safe_substitute={output.get('no_safe_substitute')}")

    # Scaling: recompute the truth from the deterministic tool and compare the factor.
    # Grams do not need to be echoed by the model - given a correct recipe_id and
    # target_servings, scale_recipe produces them exactly, and both are checked above.
    truth = call_tool(
        "scale_recipe",
        {
            "recipe_id": request["expect_recipe_id"],
            "target_servings": request["expect_target_servings"],
        },
    )
    got_factor = output.get("factor")
    try:
        if abs(float(got_factor) - truth["factor"]) > 0.001:
            failures.append(f"factor={got_factor} want {truth['factor']}")
    except (TypeError, ValueError):
        failures.append(f"factor={got_factor!r} not a number")

    return {"passed": not failures, "why": "; ".join(failures) if failures else "all checks ok"}


def run_one(system: str, request: dict[str, Any]) -> dict[str, Any]:
    """Run one system on one request and score it."""
    result = SYSTEMS[system](request["request"])
    result["request_id"] = request["request_id"]
    result["klass"] = request["klass"]
    result.update(score(request, result["output"]))
    return result


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The four numbers for one system."""
    if not rows:
        return {}
    latencies = [row["latency_seconds"] for row in rows]
    return {
        "n": len(rows),
        "pass_rate": sum(1 for row in rows if row["passed"]) / len(rows),
        "p50_latency_s": round(statistics.median(latencies), 3),
        "total_tokens": sum(row["total_tokens"] for row in rows),
        "cost_per_request_usd": sum(row["cost_usd"] for row in rows) / len(rows),
        "total_model_calls": sum(row["model_calls"] for row in rows),
    }


def write_csv(results: dict[str, Any]) -> None:
    """Write the per-run detail plus the two summary rows."""
    with CSV_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["system", "request_id", "klass", "passed", "why", "model_calls",
             "total_tokens", "cost_usd", "latency_seconds", "stop_reason"]
        )
        for key in sorted(results):
            row = results[key]
            writer.writerow([
                row["system"], row["request_id"], row["klass"], row["passed"], row["why"],
                row["model_calls"], row["total_tokens"], f"{row['cost_usd']:.6f}",
                row["latency_seconds"], row["stop_reason"],
            ])
        writer.writerow([])
        writer.writerow(["SUMMARY", "n", "pass_rate", "p50_latency_s", "total_tokens",
                         "cost_per_request_usd", "total_model_calls"])
        for system in SYSTEMS:
            rows = [r for r in results.values() if r["system"] == system]
            s = summarise(rows)
            if s:
                writer.writerow([system, s["n"], f"{s['pass_rate']:.2f}", s["p50_latency_s"],
                                 s["total_tokens"], f"{s['cost_per_request_usd']:.6f}",
                                 s["total_model_calls"]])


def print_table(results: dict[str, Any]) -> None:
    """Print the comparable table plus a by-class pass-rate breakdown."""
    print(f"\n{'system':<10} {'n':>3} {'pass':>6} {'p50 s':>7} {'tokens':>8} {'$/req':>9} {'calls':>6}")
    for system in SYSTEMS:
        rows = [r for r in results.values() if r["system"] == system]
        s = summarise(rows)
        if not s:
            print(f"{system:<10}   -  (not run yet)")
            continue
        print(f"{system:<10} {s['n']:>3} {s['pass_rate']:>5.0%} {s['p50_latency_s']:>7.2f} "
              f"{s['total_tokens']:>8} {s['cost_per_request_usd']:>9.6f} {s['total_model_calls']:>6}")

    print("\npass rate by request class")
    classes = sorted({r["klass"] for r in results.values()})
    print(f"{'class':<15} " + " ".join(f"{s:>10}" for s in SYSTEMS))
    for klass in classes:
        cells = []
        for system in SYSTEMS:
            rows = [r for r in results.values() if r["system"] == system and r["klass"] == klass]
            cells.append(f"{sum(1 for r in rows if r['passed'])}/{len(rows)}" if rows else "-")
        print(f"{klass:<15} " + " ".join(f"{c:>10}" for c in cells))

    failing = [r for r in results.values() if not r["passed"]]
    if failing:
        print("\nfailures")
        for row in sorted(failing, key=lambda r: (r["system"], r["request_id"])):
            print(f"  {row['system']:<9} {row['request_id']} ({row['klass']}) - {row['why']}")


def main() -> None:
    """Run any missing (system, request) pairs, then report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=[*SYSTEMS, "both"], default="both")
    parser.add_argument("--only", nargs="*", help="limit to these request_ids")
    parser.add_argument("--report", action="store_true", help="report stored results, run nothing")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS,
                        help="seconds to wait between runs so the per-minute limit resets")
    args = parser.parse_args()

    requests = load_requests()
    if args.only:
        requests = [r for r in requests if r["request_id"] in args.only]
    results = load_results()

    if not args.report:
        systems = list(SYSTEMS) if args.system == "both" else [args.system]
        pending = [
            (system, request)
            for system in systems
            for request in requests
            if f"{system}:{request['request_id']}" not in results
        ]
        print(f"{len(pending)} run(s) pending, pacing {args.pace:.0f}s between runs")
        for index, (system, request) in enumerate(pending):
            if index:
                time.sleep(args.pace)
            try:
                row = run_one(system, request)
            except Exception as error:
                if not is_rate_limit_error(error):
                    raise
                print(f"\nquota spent; {len(results)} runs stored, rerun to continue")
                break
            results[f"{system}:{request['request_id']}"] = row
            RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(f"  {system:<9} {request['request_id']}  "
                  f"{'PASS' if row['passed'] else 'FAIL'}  calls={row['model_calls']}  "
                  f"tokens={row['total_tokens']}  {row['latency_seconds']}s")

    if results:
        write_csv(results)
        print_table(results)
        print(f"\nwrote {CSV_FILE.name} ({len(results)} runs)")
    else:
        print("no results yet")


if __name__ == "__main__":
    main()
