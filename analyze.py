"""Evidence behind the chunker choice: usable-answer grading and top-1 failures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ANSWER_KEYS_FILE = Path(__file__).parent / "answer_keys.json"
RETRIEVAL_JSON = Path(__file__).parent / "retrieval_results.json"
COLLECTIONS = ("baseline", "structure_aware")


def _flat(text: str) -> str:
    """Collapse all whitespace so wrapped source lines still match a key phrase."""
    return " ".join(text.split())


def grade_row(row: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    """Grade one question: is the answer value present, and is it usable in context."""
    value_hit = False
    usable_hit = False
    winning_chunk = ""
    for hit in row["results"]:
        text = _flat(hit["text"])
        if _flat(key["value"]) not in text:
            continue
        value_hit = True
        header_ok = key["table_header"] is None or _flat(key["table_header"]) in text
        title_ok = _flat(key["title"]) in text
        if header_ok and title_ok:
            usable_hit = True
            winning_chunk = hit["chunk_id"]
            break
        if not winning_chunk:
            winning_chunk = hit["chunk_id"]
    return {
        "id": row["id"],
        "needs_table_row": row["needs_table_row"],
        "value_hit": value_hit,
        "usable_hit": usable_hit,
        "chunk": winning_chunk,
    }


def print_grounding(data: dict[str, Any], keys: dict[str, Any]) -> None:
    """Print the value_hit / usable_hit comparison for both chunkers."""
    graded = {
        label: [grade_row(row, keys[row["id"]]) for row in data[label]]
        for label in COLLECTIONS
    }
    print("=== does the retrieved text carry the answer, usably? ===")
    print("| qid | table_row | base value | base usable | struct value | struct usable |")
    print("|---|---|---|---|---|---|")
    for base, struct in zip(graded["baseline"], graded["structure_aware"]):
        print(
            f"| {base['id']} | {base['needs_table_row']} | {base['value_hit']} | "
            f"{base['usable_hit']} | {struct['value_hit']} | {struct['usable_hit']} |"
        )
    for label in COLLECTIONS:
        rows = graded[label]
        table_rows = [r for r in rows if r["needs_table_row"]]
        print(
            f"\n{label}: value_hit {sum(1 for r in rows if r['value_hit'])}/8, "
            f"usable_hit {sum(1 for r in rows if r['usable_hit'])}/8, "
            f"usable_hit on table questions {sum(1 for r in table_rows if r['usable_hit'])}"
            f"/{len(table_rows)}"
        )


def print_failures(data: dict[str, Any]) -> None:
    """Print top-1 correctness and the rank of the first correct chunk per question."""
    for label in COLLECTIONS:
        print(f"\n=== {label}: top-1 correctness ===")
        for row in data[label]:
            expected = row["expected_recipe_id"]
            ranks = [h["rank"] for h in row["results"] if h["recipe_id"] == expected]
            wrong_top1 = row["top1_recipe_id"] != expected
            print(
                f"{row['id']}: top1={row['top1_recipe_id']} "
                f"{'WRONG' if wrong_top1 else 'ok'} "
                f"first_correct_rank={ranks[0] if ranks else 'none'} "
                f"n_correct_in_top5={len(ranks)} "
                f"top1_score={row['results'][0]['score']}"
            )


def main() -> None:
    """Print both analyses from the stored retrieval results."""
    data = json.loads(RETRIEVAL_JSON.read_text(encoding="utf-8"))
    keys = json.loads(ANSWER_KEYS_FILE.read_text(encoding="utf-8"))
    print_grounding(data, keys)
    print_failures(data)


if __name__ == "__main__":
    main()
