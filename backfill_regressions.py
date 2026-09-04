"""Fill the regression cases from their real recorded traces instead of re-calling the model.

A regression case exists to pin a failure that already happened. Re-generating it would
cost a call and might not reproduce the bug, so the stored trace is the better source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from run_substitutions import OUTPUTS_FILE, load_cases, load_outputs

TRACES_FILE = Path(__file__).parent / "traces.jsonl"
TRACE_KEY = "replayed_from_trace"


def load_traces(path: Path = TRACES_FILE) -> dict[str, Any]:
    """Index every stored trace by its trace_id."""
    traces = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            trace = json.loads(line)
            traces[trace["trace_id"]] = trace
    return traces


def main() -> None:
    """Copy each regression case's recorded output into the substitution outputs."""
    traces = load_traces()
    outputs = load_outputs()
    added = []
    for case in load_cases():
        trace_id = case.get(TRACE_KEY)
        if not trace_id or case["case_id"] in outputs:
            continue
        if trace_id not in traces:
            print(f"  {case['case_id']}: trace {trace_id} not found in traces.jsonl")
            continue
        trace = traces[trace_id]
        outputs[case["case_id"]] = {
            "case_id": case["case_id"],
            "request": case["request"],
            "mode": case["mode"],
            "kind": case["kind"],
            "recipe_id": case["recipe_id"],
            "trace_id": trace_id,
            "answer": trace["raw_output"],
            "refused": trace["refused"],
            "retrieved": [
                {"chunk_id": c["chunk_id"], "rank": c["rank"], "score": c["score"]}
                for c in trace["retrieved"]
            ],
            "citation_checks": trace["citation_checks"],
            # Marked so nobody later mistakes this for a fresh generation.
            "source": "recorded_trace",
        }
        added.append(case["case_id"])

    if added:
        OUTPUTS_FILE.write_text(json.dumps(outputs, indent=2), encoding="utf-8")
    print(f"backfilled {len(added)} regression case(s) from recorded traces: "
          f"{', '.join(added) if added else 'none'}")
    print(f"{len(outputs)} outputs total, 0 API calls spent")


if __name__ == "__main__":
    main()
