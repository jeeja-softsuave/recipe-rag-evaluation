"""Index the 6 new cards under both chunkers and compare retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from recipe_rag import (
    BASELINE_COLLECTION,
    STRUCTURE_AWARE_COLLECTION,
    TOP_K,
    build_index,
    chunk_baseline,
    chunk_structure_aware,
    load_recipe_cards,
    run_retrieval_eval,
    search,
    search_with_dietary_filter,
)

QUESTIONS_FILE = Path(__file__).parent / "eval_questions.json"
SEARCH_DUMP_FILE = Path(__file__).parent / "search_dump.md"
RETRIEVAL_JSON = Path(__file__).parent / "retrieval_results.json"
FILTER_QUERY = "how much curd do I need"
FILTER_TAG = "vegan"


def format_row_table(baseline: list[dict[str, Any]], structure: list[dict[str, Any]]) -> str:
    """Render the per-question hit table with both totals."""
    lines = [
        "| question_id | expected_recipe_id | baseline_hit | structure_aware_hit |",
        "|---|---|---|---|",
    ]
    for base, struct in zip(baseline, structure):
        lines.append(
            f"| {base['id']} | {base['expected_recipe_id']} | "
            f"{str(base['hit']).lower()} | {str(struct['hit']).lower()} |"
        )
    base_total = sum(1 for row in baseline if row["hit"])
    struct_total = sum(1 for row in structure if row["hit"])
    lines.append("")
    lines.append(f"baseline hit_in_top_5: {base_total} out of {len(baseline)}")
    lines.append(f"structure_aware hit_in_top_5: {struct_total} out of {len(structure)}")
    return "\n".join(lines)


def format_result_list(results: list[dict[str, Any]]) -> str:
    """Render one ranked result list as a markdown table."""
    lines = [
        "| rank | chunk_id | recipe_id | section | dietary_tags | score |",
        "|---|---|---|---|---|---|",
    ]
    for hit in results:
        lines.append(
            f"| {hit['rank']} | {hit['chunk_id']} | {hit['recipe_id']} | "
            f"{hit['section']} | {hit['dietary_tags']} | {hit['score']} |"
        )
    return "\n".join(lines)


def main() -> None:
    """Build both indexes, run all 8 questions, and dump every raw result list."""
    cards = load_recipe_cards()
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))

    baseline_chunks = [chunk for card in cards for chunk in chunk_baseline(card)]
    structure_chunks = [chunk for card in cards for chunk in chunk_structure_aware(card)]
    print(f"cards indexed: {len(cards)} (only {[c['source_file'] for c in cards]})")
    print(f"baseline chunks: {len(baseline_chunks)}")
    print(f"structure_aware chunks: {len(structure_chunks)}")

    baseline_collection = build_index(BASELINE_COLLECTION, baseline_chunks)
    structure_collection = build_index(STRUCTURE_AWARE_COLLECTION, structure_chunks)

    baseline_rows = run_retrieval_eval(questions, baseline_collection, TOP_K)
    structure_rows = run_retrieval_eval(questions, structure_collection, TOP_K)

    print()
    print(format_row_table(baseline_rows, structure_rows))

    unfiltered = search(structure_collection, FILTER_QUERY, TOP_K)
    filtered = search_with_dietary_filter(structure_collection, FILTER_QUERY, FILTER_TAG, TOP_K)
    print()
    print(f"FILTER QUERY: {FILTER_QUERY!r}   tag={FILTER_TAG}")
    print("UNFILTERED")
    print(format_result_list(unfiltered))
    print("FILTERED")
    print(format_result_list(filtered))
    print(f"top1 changed: {unfiltered[0]['chunk_id'] != filtered[0]['chunk_id']}")

    dump = ["# Raw search results (top_k = %d)" % TOP_K, ""]
    dump.append("Only the 6 new fermentation cards are indexed in either collection.")
    for label, rows in (("recipes_baseline", baseline_rows), ("recipes_structure_aware", structure_rows)):
        dump.append(f"\n## Collection: {label}\n")
        for row in rows:
            dump.append(f"### {row['id']} — {row['question']}")
            dump.append(
                f"expected_recipe_id: `{row['expected_recipe_id']}` · "
                f"expected_section: `{row['expected_section']}` · "
                f"needs_table_row: {row['needs_table_row']} · hit: **{row['hit']}**"
            )
            dump.append("")
            dump.append(format_result_list(row["results"]))
            dump.append("")
            for hit in row["results"]:
                dump.append(f"<details><summary>{hit['chunk_id']}</summary>\n")
                dump.append("```")
                dump.append(hit["text"])
                dump.append("```")
                dump.append("</details>")
            dump.append("")
    dump.append("\n## Dietary filter comparison\n")
    dump.append(f"query: `{FILTER_QUERY}` · tag: `{FILTER_TAG}`\n")
    dump.append("**Unfiltered**\n")
    dump.append(format_result_list(unfiltered))
    dump.append("\n**Filtered**\n")
    dump.append(format_result_list(filtered))
    SEARCH_DUMP_FILE.write_text("\n".join(dump), encoding="utf-8")

    RETRIEVAL_JSON.write_text(
        json.dumps(
            {
                "baseline": baseline_rows,
                "structure_aware": structure_rows,
                "filter_query": FILTER_QUERY,
                "filter_tag": FILTER_TAG,
                "unfiltered": unfiltered,
                "filtered": filtered,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {SEARCH_DUMP_FILE.name} and {RETRIEVAL_JSON.name}")


if __name__ == "__main__":
    main()
