"""Run the whole eval suite against the production app at one prompt version.

The suite is the Week 6 suite plus every case added since: substitution_cases.jsonl (34)
and eval_cases_week11.jsonl. Every case is regenerated through observe.answer_observed
with the given prompt version, scored by every deterministic assertion in assertions.py,
and judged by judge_v2 unchanged. A case passes only if all assertions pass and the judge
says PASS - the same rule run_eval.py uses.

Resumable per prompt version: outputs go to suite_outputs_<version>.json as they finish.

    python run_suite.py --prompt v2 --key 4 --model gemini-3.5-flash-lite --no-judge
    python run_suite.py --prompt v2 --model gemini-3.5-flash-lite --report-only   # no calls

Outputs are kept per prompt version AND generation model, so runs on different models
never mix. The judge is always judge_v2 on the Week 6 judge model, whatever generated.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from assertions import ASSERTIONS, run_assertions
from make_labels import chunk_texts
from observe import _generate, answer_observed, collection
from recipe_rag import GEMINI_MODEL, is_rate_limit_error
from run_judge import judge_prompt, parse_verdicts, render_case

PROJECT_DIR = Path(__file__).parent
CASE_FILES = [PROJECT_DIR / "substitution_cases.jsonl", PROJECT_DIR / "eval_cases_week11.jsonl"]
JUDGE_VERSION = "v2"
# 18 cases per judge call: two calls per suite run instead of four.
JUDGE_BATCH_SIZE = 18
EVAL_USER = "eval-suite"


def load_suite() -> list[dict[str, Any]]:
    """Every case in every suite file that exists, in file order."""
    cases = []
    for path in CASE_FILES:
        if path.exists():
            cases += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
    return cases


def outputs_file(version: str, model: str) -> Path:
    """Where one prompt version's suite outputs, from one generation model, live."""
    return PROJECT_DIR / f"suite_outputs_{version}_{model}.json"


def generate(cases: list[dict[str, Any]], version: str, model: str, pace: float) -> bool:
    """Generate every missing output. Returns False if the quota ran out."""
    path = outputs_file(version, model)
    outputs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    index = collection()
    for case in cases:
        if case["case_id"] in outputs:
            continue
        try:
            record = answer_observed(case["request"], EVAL_USER, version, index=index, model=model)
        except Exception as error:
            if is_rate_limit_error(error):
                print(f"quota spent; {len(outputs)}/{len(cases)} generated - rerun with another --key")
                return False
            raise
        outputs[case["case_id"]] = {
            **{key: case[key] for key in ("case_id", "request", "mode", "kind", "recipe_id")},
            "trace_id": record["trace_id"], "prompt_version": version, "model": model,
            "answer": record["answer"], "refused": record["refused"],
            "retrieved": [{"chunk_id": cid, "rank": rank, "score": score} for rank, (cid, score)
                          in enumerate(zip(record["context_ids"], record["context_scores"]), 1)],
        }
        path.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {case['case_id']:<6} refused={record['refused']!s:<5} {case['request'][:60]}")
        time.sleep(pace)
    return True


def judge(cases: list[dict[str, Any]], version: str, model: str, judge_model: str) -> bool:
    """Judge every output that has no verdict yet, in batches. False if the quota ran out."""
    path = outputs_file(version, model)
    outputs = json.loads(path.read_text(encoding="utf-8"))
    pending = [c["case_id"] for c in cases if "verdict" not in outputs[c["case_id"]]]
    index = collection()
    system_prompt = judge_prompt(JUDGE_VERSION)
    for start in range(0, len(pending), JUDGE_BATCH_SIZE):
        batch = pending[start : start + JUDGE_BATCH_SIZE]
        texts = chunk_texts(index, [c["chunk_id"] for cid in batch for c in outputs[cid]["retrieved"]])
        try:
            raw, _, _ = _generate(system_prompt, "\n\n".join(render_case(outputs[cid], texts)
                                                              for cid in batch), judge_model)
        except Exception as error:
            if is_rate_limit_error(error):
                print("quota spent while judging - rerun with another --key")
                return False
            raise
        parsed = parse_verdicts(raw)
        for cid in batch:
            outputs[cid]["verdict"] = parsed.get(cid, {}).get("verdict", "NO_VERDICT")
            outputs[cid]["judge_reason"] = parsed.get(cid, {}).get("reason", "")
            outputs[cid]["judge_model"] = judge_model
        path.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  judged {batch[0]}..{batch[-1]}")
    return True


def report(cases: list[dict[str, Any]], version: str, model: str, label: str) -> None:
    """Pass counts over the whole suite - assertions alone, and with the judge - saved."""
    outputs = json.loads(outputs_file(version, model).read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        output = outputs.get(case["case_id"])
        if output is None:
            rows.append({"case_id": case["case_id"], "assertions_pass": False, "judge": None,
                         "passed": False, "why": ["not generated"]})
            continue
        checks = run_assertions(output)
        failed = [f"{name}: {result['detail']}" for name, result in checks.items()
                  if not result["passed"]]
        verdict = output.get("verdict")
        if verdict not in (None, "PASS"):
            failed.append(f"judge {verdict}: {output.get('judge_reason', '')}")
        asserted = not any(not result["passed"] for result in checks.values())
        rows.append({"case_id": case["case_id"], "assertions_pass": asserted, "judge": verdict,
                     "passed": not failed and verdict == "PASS", "why": failed})
    asserted_count = sum(row["assertions_pass"] for row in rows)
    judge_models = sorted({o.get("judge_model", GEMINI_MODEL) for o in outputs.values()
                           if o.get("verdict")}) or [GEMINI_MODEL]
    judge_label = f"judge_{JUDGE_VERSION} on {', '.join(judge_models)}"
    judged_all = all(row["judge"] is not None for row in rows)
    full = sum(row["passed"] for row in rows)
    print(f"SUITE {label}  prompt {version}  generated by {model}")
    print(f"  assertions only ({len(ASSERTIONS)} checks): {asserted_count}/{len(rows)} passed")
    print(f"  assertions + {judge_label}: "
          + (f"{full}/{len(rows)} passed" if judged_all else "judge not run yet"))
    for row in rows:
        if row["why"]:
            print(f"  FAIL {row['case_id']:<6} " + " | ".join(row["why"])[:220])
    (PROJECT_DIR / f"suite_report_{label}.json").write_text(json.dumps(
        {"label": label, "prompt_version": version, "generation_model": model,
         "judge": judge_label, "assertions": list(ASSERTIONS),
         "assertions_passed": asserted_count, "judged": judged_all,
         "passed_with_judge": full if judged_all else None, "total": len(rows), "cases": rows},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """Generate, judge and report one suite run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="prompt version to test, e.g. v2")
    parser.add_argument("--label", help="name for the report file; defaults to the version")
    parser.add_argument("--key", type=int, default=1)
    parser.add_argument("--model", default=GEMINI_MODEL, help="generation model for the app")
    parser.add_argument("--pace", type=float, default=0.0, help="seconds between generations")
    parser.add_argument("--judge-model", default=GEMINI_MODEL,
                        help="model that runs judge_v2; the Week 6 judge used the default")
    parser.add_argument("--no-judge", action="store_true", help="generate and assert only")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    cases = load_suite()
    if not args.report_only:
        name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
        os.environ["GEMINI_API_KEY"] = os.environ[name]
        if not generate(cases, args.prompt, args.model, args.pace):
            return
        if not args.no_judge and not judge(cases, args.prompt, args.model, args.judge_model):
            return
    report(cases, args.prompt, args.model, args.label or args.prompt)


if __name__ == "__main__":
    main()
