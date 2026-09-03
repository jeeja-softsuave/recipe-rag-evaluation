"""Run every substitution case through the real app pipeline and store the outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import CHROMA_DIR, STRUCTURE_AWARE_COLLECTION, is_rate_limit_error
from tracing import answer_and_trace

CASES_FILE = Path(__file__).parent / "substitution_cases.jsonl"
OUTPUTS_FILE = Path(__file__).parent / "substitution_outputs.json"


def load_cases(path: Path = CASES_FILE) -> list[dict[str, Any]]:
    """Load the substitution eval cases, one JSON object per line."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_outputs(path: Path = OUTPUTS_FILE) -> dict[str, Any]:
    """Load whatever outputs already exist, so a spent quota is not fatal."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    """Generate any missing substitution output, appending as it goes."""
    cases = load_cases()
    outputs = load_outputs()
    pending = [case for case in cases if case["case_id"] not in outputs]
    print(f"{len(cases)} cases, {len(outputs)} already generated, {len(pending)} to go")

    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )
    for case in pending:
        try:
            trace = answer_and_trace(collection, case["request"], source="week6")
        except Exception as error:
            if not is_rate_limit_error(error):
                raise
            print(f"\nquota spent; {len(outputs)} of {len(cases)} done, rerun to continue")
            break
        outputs[case["case_id"]] = {
            "case_id": case["case_id"],
            "request": case["request"],
            "mode": case["mode"],
            "kind": case["kind"],
            "recipe_id": case["recipe_id"],
            "trace_id": trace["trace_id"],
            "answer": trace["raw_output"],
            "refused": trace["refused"],
            "retrieved": [
                {"chunk_id": chunk["chunk_id"], "rank": chunk["rank"], "score": chunk["score"]}
                for chunk in trace["retrieved"]
            ],
            "citation_checks": trace["citation_checks"],
        }
        # Written after every call so an interrupted run loses nothing.
        OUTPUTS_FILE.write_text(json.dumps(outputs, indent=2), encoding="utf-8")
        print(f"  {case['case_id']}  refused={trace['refused']}  {case['request'][:52]}")

    print(f"\n{len(outputs)}/{len(cases)} outputs in {OUTPUTS_FILE.name}")


if __name__ == "__main__":
    main()
