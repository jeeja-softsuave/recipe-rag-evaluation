"""Bonus: compare the top failure mode's frequency in the random sample vs the demo set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tracing import load_traces

RANDOM_SAMPLE_FILE = Path(__file__).parent / "sample_random.json"
DEMO_SAMPLE_FILE = Path(__file__).parent / "sample_demo.json"
RESULTS_FILE = Path(__file__).parent / "bonus_demo_vs_random.json"
CHUNK_ID_SEPARATOR = "::"
PERCENT_DECIMALS = 0


def about_recipe_lookup() -> dict[str, str]:
    """Map each sampled question to the recipe it asks about, where that is known."""
    payload = json.loads(RANDOM_SAMPLE_FILE.read_text(encoding="utf-8"))
    return {item["question"]: item["about_recipe_id"] for item in payload["sample"]}


def has_unchecked_citation(trace: dict[str, Any]) -> bool:
    """M3: a citation was verified without any claimed value being extracted."""
    return any(check["claimed_values"] == [] for check in trace["citation_checks"])


def has_voided_citation(trace: dict[str, Any]) -> bool:
    """M4: not a refusal, yet the citation regex extracted nothing at all."""
    return not trace["refused"] and not trace["citation_checks"]


def has_foreign_chunk(trace: dict[str, Any], asked_recipe: str) -> bool:
    """M5: a chunk from a recipe the question was not about appeared in the top-k."""
    if not asked_recipe:
        return False
    recipes = {chunk["chunk_id"].split(CHUNK_ID_SEPARATOR)[0] for chunk in trace["retrieved"]}
    return bool(recipes - {asked_recipe})


def summarise(traces: list[dict[str, Any]], asked: dict[str, str]) -> dict[str, Any]:
    """Count each automatable mode across a set of traces."""
    total = len(traces)
    counts = {
        "M3 citation check passes while checking nothing": sum(
            1 for trace in traces if has_unchecked_citation(trace)
        ),
        "M4 two chunk ids in one bracket void the check": sum(
            1 for trace in traces if has_voided_citation(trace)
        ),
        "M5 another recipe's chunk in the top-k": sum(
            1 for trace in traces if has_foreign_chunk(trace, asked.get(trace["question"], ""))
        ),
        "refused": sum(1 for trace in traces if trace["refused"]),
    }
    return {
        "total": total,
        "counts": counts,
        "percent": {
            name: round(100 * count / total, PERCENT_DECIMALS) if total else 0.0
            for name, count in counts.items()
        },
    }


def main() -> None:
    """Print the two frequencies side by side for every automatable mode."""
    traces = load_traces()
    demo_questions = {
        item["question"]
        for item in json.loads(DEMO_SAMPLE_FILE.read_text(encoding="utf-8"))["sample"]
    }
    random_traces = [trace for trace in traces if trace["source"] == "random"]
    demo_traces = [trace for trace in traces if trace["source"] == "demo"]
    asked = about_recipe_lookup()

    random_summary = summarise(random_traces, asked)
    demo_summary = summarise(demo_traces, asked)

    print(f"random sample: {random_summary['total']} traces")
    print(f"demo sample:   {demo_summary['total']} traces "
          f"(of {len(demo_questions)} demo questions drawn)")
    if demo_summary["total"] < len(demo_questions):
        print(f"  incomplete - rerun run_traces.py --set demo for the remaining "
              f"{len(demo_questions) - demo_summary['total']}")
    print()
    print("| mode | random sample | demo set |")
    print("|---|---|---|")
    for name in random_summary["counts"]:
        random_count = random_summary["counts"][name]
        demo_count = demo_summary["counts"][name]
        print(
            f"| {name} | {random_count}/{random_summary['total']} "
            f"({random_summary['percent'][name]:.0f}%) | {demo_count}/{demo_summary['total']} "
            f"({demo_summary['percent'][name]:.0f}%) |"
        )

    RESULTS_FILE.write_text(
        json.dumps({"random": random_summary, "demo": demo_summary}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    main()
