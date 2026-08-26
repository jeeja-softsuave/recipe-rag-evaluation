"""Generate one trace per sampled question, resumable so a spent quota is not fatal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import CHROMA_DIR, STRUCTURE_AWARE_COLLECTION, is_rate_limit_error
from tracing import TRACES_FILE, answer_and_trace, load_traces

SAMPLE_FILES = {
    "random": Path(__file__).parent / "sample_random.json",
    "demo": Path(__file__).parent / "sample_demo.json",
}


def load_sample(name: str) -> list[dict[str, Any]]:
    """Load one seeded sample by name."""
    payload = json.loads(SAMPLE_FILES[name].read_text(encoding="utf-8"))
    return payload["sample"]


def main() -> None:
    """Trace every sampled question that has no trace yet, then report what remains."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", choices=sorted(SAMPLE_FILES), default="random")
    arguments = parser.parse_args()

    sample = load_sample(arguments.set)
    already_traced = {trace["question"] for trace in load_traces()}
    pending = [item for item in sample if item["question"] not in already_traced]
    print(f"{arguments.set} sample: {len(sample)} questions, {len(pending)} still to trace")

    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )
    written = 0
    for item in pending:
        try:
            trace = answer_and_trace(collection, item["question"], source=arguments.set)
        except Exception as error:
            if not is_rate_limit_error(error):
                raise
            print(f"\nquota spent after {written} new trace(s); rerun later to continue")
            break
        written += 1
        print(f"  {trace['trace_id']}  refused={trace['refused']}  {item['question'][:58]}")

    total = len(load_traces())
    print(f"\n{written} new trace(s) written · {total} total in {TRACES_FILE.name}")
    if total < len(sample):
        print(f"still need {len(sample) - total} more; rerun this script when quota resets")


if __name__ == "__main__":
    main()
