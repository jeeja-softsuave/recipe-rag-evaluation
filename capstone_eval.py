"""The Week 6 eval suite, run against the INTEGRATED system, in one command.

    python capstone_eval.py --label before --key 1     # run, assert, judge, report
    python capstone_eval.py --label before --report    # no API calls
    python capstone_eval.py --label before --agreement capstone/labels_before.json

Order of operations, as in Week 6: every case runs through pantry.answer (the same entry
point a user hits); the deterministic assertions score it FIRST; then judge_v2 (unchanged)
judges groundedness against the tool results that run obtained. Allergen correctness is
never judged: it is asserted from the declaration fields.

Also reports, from the same runs and with no extra calls: pass rate per taxonomy group, the
allergy cases on their own, and the Week 8 trajectory numbers (tool-choice accuracy and the
outcome-vs-trajectory gap; alternate valid paths are accepted as sets).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pantry
from capstone_assertions import ASSERTIONS, run_assertions
from observe import _generate
from run_judge import judge_prompt, parse_verdicts

PROJECT_DIR = Path(__file__).parent
CASES_FILE = PROJECT_DIR / "capstone" / "cases.jsonl"
OUT_DIR = PROJECT_DIR / "capstone" / "runs"
JUDGE_VERSION = "v2"
JUDGE_BATCH = 10


def load_cases(path: Path = CASES_FILE) -> list[dict[str, Any]]:
    """The suite, in file order."""
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def outputs_path(label: str) -> Path:
    """Where one labelled run's records live."""
    return OUT_DIR / f"outputs_{label}.json"


def run_cases(cases: list[dict[str, Any]], label: str, pace: float) -> bool:
    """Run every case not yet stored. False if the quota ran out."""
    path = outputs_path(label)
    path.parent.mkdir(parents=True, exist_ok=True)
    outputs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for case in cases:
        if case["case_id"] in outputs:
            continue
        try:
            record = asyncio.run(pantry.answer(case["question"]))
        except Exception as error:
            if pantry.is_quota_error(error):
                print(f"quota refused; {len(outputs)}/{len(cases)} cases stored - resume with another --key")
                return False
            raise
        outputs[case["case_id"]] = record
        path.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {case['case_id']:<5} {len(record['calls'])} tool calls  {record['total_tokens']:>6} tokens  "
              f"{record['latency_ms'] / 1000:5.1f}s  trace {record['trace_id']}")
        time.sleep(pace)
    return True


def render_for_judge(case_id: str, record: dict[str, Any]) -> str:
    """One case for judge_v2: question, answer, and the tool results the run obtained."""
    lines = [f"CASE {case_id}", f"QUESTION: {record['question']}",
             f"ANSWER: {record['answer'].strip() or '(empty answer)'}", "CONTEXT:"]
    if not record["calls"]:
        lines.append("  (no tool was called; there is no context)")
    for call in record["calls"]:
        lines.append(f"  [{call['tool']}({json.dumps(call['arguments'])})] {' '.join(call['result'].split())}")
    return "\n".join(lines)


def judge(cases: list[dict[str, Any]], label: str, judge_model: str) -> bool:
    """Judge every stored case without a verdict. False if the quota ran out."""
    path = outputs_path(label)
    outputs = json.loads(path.read_text(encoding="utf-8"))
    pending = [c["case_id"] for c in cases if c["case_id"] in outputs and "judge" not in outputs[c["case_id"]]]
    system_prompt = judge_prompt(JUDGE_VERSION)
    for start in range(0, len(pending), JUDGE_BATCH):
        batch = pending[start : start + JUDGE_BATCH]
        try:
            raw, _, _ = _generate(system_prompt, "\n\n".join(render_for_judge(cid, outputs[cid]) for cid in batch),
                                  judge_model)
        except Exception as error:
            if pantry.is_quota_error(error):
                print("quota refused while judging - resume with another --key")
                return False
            raise
        parsed = parse_verdicts(raw)
        for cid in batch:
            outputs[cid]["judge"] = {**parsed.get(cid, {"verdict": "NO_VERDICT", "reason": ""}),
                                     "model": judge_model, "prompt": f"judge_{JUDGE_VERSION}"}
        path.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  judged {batch[0]}..{batch[-1]}")
    return True


def trajectory(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Week 8 rule: right tool set (any accepted alternative) AND right arguments."""
    called = {call["tool"] for call in record["calls"] if not call["is_error"]}
    choice_ok = any(set(option) <= called for option in case["tools_any"])
    args_ok = True
    if case.get("recipe_id"):
        recipe_calls = [c for c in record["calls"] if c["tool"] in {"check_allergens", "scale_recipe"}]
        if recipe_calls:
            args_ok = any(c["arguments"].get("recipe_id") == case["recipe_id"] for c in recipe_calls)
    return {"called": sorted(called), "tool_choice_ok": choice_ok, "args_ok": args_ok,
            "passed": choice_ok and args_ok}


def report(cases: list[dict[str, Any]], label: str) -> dict[str, Any]:
    """Score every stored case and print the suite report. Writes capstone/runs/report_<label>.json."""
    outputs = json.loads(outputs_path(label).read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        record = outputs.get(case["case_id"])
        if record is None:
            continue
        checks = run_assertions(case, record)
        failed = [f"{n}: {r['detail']}" for n, r in checks.items() if not r["passed"]]
        verdict = (record.get("judge") or {}).get("verdict")
        rows.append({"case_id": case["case_id"], "group": case["group"], "allergy": case["allergy"],
                     "trace_id": record["trace_id"], "assertions_passed": not failed, "failed": failed,
                     "judge": verdict, "passed": not failed and verdict == "PASS",
                     "trajectory": trajectory(case, record),
                     "tokens": record["total_tokens"], "cost_usd": record["cost_usd"],
                     "latency_ms": record["latency_ms"]})

    def rate(subset: list[dict[str, Any]], key: str = "passed") -> str:
        return f"{sum(r[key] for r in subset)}/{len(subset)}" if subset else "-"

    judged = all(r["judge"] for r in rows)
    print(f"SUITE {label}: {len(rows)}/{len(cases)} cases run  |  {len(ASSERTIONS)} assertions, then "
          f"judge_{JUDGE_VERSION} {'(judged)' if judged else '(judge NOT run yet)'}")
    print(f"  overall: assertions {rate(rows, 'assertions_passed')}   assertions + judge {rate(rows)}")
    allergy = [r for r in rows if r["allergy"]]
    print(f"  ALLERGY CASES ({len(allergy)}): assertions {rate(allergy, 'assertions_passed')}   with judge {rate(allergy)}")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    for group, subset in sorted(groups.items()):
        print(f"    {group:<13} n={len(subset):<3} assertions {rate(subset, 'assertions_passed'):<6} with judge {rate(subset)}")
    traj = [r["trajectory"] for r in rows]
    outcome = sum(r["passed"] for r in rows) / len(rows) if rows else 0
    traj_rate = sum(t["passed"] for t in traj) / len(traj) if traj else 0
    print(f"  trajectory: tool-choice accuracy {sum(t['tool_choice_ok'] for t in traj)}/{len(traj)}   "
          f"trajectory pass {traj_rate:.0%}   outcome pass {outcome:.0%}   GAP {outcome - traj_rate:+.0%}")
    if rows:
        print(f"  cost/query ${sum(r['cost_usd'] for r in rows) / len(rows):.6f}   "
              f"mean tokens {sum(r['tokens'] for r in rows) / len(rows):.0f}")
    for row in rows:
        if not row["passed"]:
            why = row["failed"] + ([f"judge {row['judge']}"] if row["judge"] and row["judge"] != "PASS" else [])
            print(f"  FAIL {row['case_id']:<5} {row['trace_id']}  " + " | ".join(why)[:200])
    summary = {"label": label, "n": len(rows), "judged": judged, "rows": rows,
               "assertions_passed": sum(r["assertions_passed"] for r in rows),
               "passed": sum(r["passed"] for r in rows),
               "allergy_n": len(allergy), "allergy_passed": sum(r["passed"] for r in allergy),
               "tool_choice_accuracy": sum(t["tool_choice_ok"] for t in traj) / len(traj) if traj else None,
               "gap": outcome - traj_rate}
    (OUT_DIR / f"report_{label}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    return summary


def agreement(label: str, labels_file: Path) -> None:
    """Judge vs hand labels on the integrated outputs: agreement as a number, and both error directions."""
    outputs = json.loads(outputs_path(label).read_text(encoding="utf-8"))
    labels = json.loads(labels_file.read_text(encoding="utf-8"))["labels"]
    pairs = [(cid, human, (outputs[cid].get("judge") or {}).get("verdict")) for cid, human in labels.items()
             if cid in outputs]
    agree = sum(human == judged for _, human, judged in pairs)
    lenient = [cid for cid, human, judged in pairs if human == "FAIL" and judged == "PASS"]
    strict = [cid for cid, human, judged in pairs if human == "PASS" and judged == "FAIL"]
    print(f"judge agreement {agree}/{len(pairs)} = {agree / len(pairs):.0%}  (gate: 85%)")
    print(f"  too lenient (human FAIL, judge PASS): {lenient}")
    print(f"  too strict  (human PASS, judge FAIL): {strict}")


def main() -> None:
    """Run, judge, report; or report / agreement only."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True)
    parser.add_argument("--cases", type=Path, default=CASES_FILE,
                        help="case file; capstone/redteam_cases.jsonl for the injection suite")
    parser.add_argument("--key", type=int, default=1)
    parser.add_argument("--pace", type=float, default=5.0)
    parser.add_argument("--judge-model", default=pantry.MODEL)
    parser.add_argument("--report", action="store_true", help="report only, no API calls")
    parser.add_argument("--agreement", type=Path, help="hand-labels file to compare the judge against")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if args.agreement:
        agreement(args.label, args.agreement)
        return
    if not args.report:
        name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
        os.environ["GEMINI_API_KEY"] = os.environ[name]
        if not (run_cases(cases, args.label, args.pace) and judge(cases, args.label, args.judge_model)):
            return
    report(cases, args.label)


if __name__ == "__main__":
    main()
