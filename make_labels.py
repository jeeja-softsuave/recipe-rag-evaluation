"""Print a blind labelling worksheet and write an empty label file to fill in."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import CHROMA_DIR, STRUCTURE_AWARE_COLLECTION
from run_substitutions import load_cases, load_outputs

WORKSHEET_FILE = Path(__file__).parent / "labels_worksheet.md"
LABELS_FILE = Path(__file__).parent / "labels_25.json"
PLACEHOLDER = "PASS_OR_FAIL"
CRITERION = (
    "SUPPORTED: every substitution or swap the answer proposes is supported by the recipe "
    "context below, and the answer does not introduce an allergen or food-safety risk that "
    "the context does not license. A refusal (NOT_IN_CORPUS) is SUPPORTED when the context "
    "genuinely has no substitution for what was asked, and NOT SUPPORTED when it does."
)


def chunk_texts(collection: Any, chunk_ids: list[str]) -> dict[str, str]:
    """Fetch the text of each retrieved chunk so the labeller sees the same evidence."""
    # Deduplicated because a batch of cases usually retrieves some of the same chunks,
    # and Chroma rejects a get() whose id list repeats.
    unique_ids = sorted(set(chunk_ids))
    if not unique_ids:
        return {}
    stored = collection.get(ids=unique_ids, include=["documents"])
    return dict(zip(stored["ids"], stored["documents"]))


def main() -> None:
    """Write the labelling worksheet and an unfilled labels_25.json skeleton."""
    cases = {case["case_id"]: case for case in load_cases()}
    outputs = load_outputs()
    # Every generated case is labelled, replays included: a case the human does not
    # label cannot contribute to the agreement measurement.
    to_label = [case_id for case_id in sorted(cases) if case_id in outputs]
    missing = [case_id for case_id in sorted(cases) if case_id not in outputs]

    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )

    lines = [
        "# Blind labelling worksheet",
        "",
        "Mark every case PASS or FAIL on this one criterion, then write your verdicts into",
        "`labels_25.json`. The judge has not been run and its verdicts do not exist yet.",
        "",
        "## The criterion",
        "",
        CRITERION,
        "",
        "Judge nothing else. Not wording, not tone, not completeness, not citation format, not",
        "whether numbers parse — those are checked by assertions, not by you.",
        "",
    ]
    if missing:
        lines += [
            f"**{len(missing)} case(s) not yet generated: {', '.join(missing)}.** "
            "Rerun `run_substitutions.py` when the quota resets, then regenerate this worksheet.",
            "",
        ]
    lines.append("---")

    for case_id in to_label:
        output = outputs[case_id]
        lines += [
            "",
            f"## {case_id} — PASS / FAIL ?",
            "",
            f"**Asked:** {output['request']}",
            "",
            "**The app answered:**",
            "",
            "```",
            output["answer"].strip(),
            "```",
            "",
            "**Recipe context it was given** (this is all it could see):",
            "",
        ]
        texts = chunk_texts(collection, [c["chunk_id"] for c in output["retrieved"]])
        for chunk in output["retrieved"]:
            body = " ".join(texts.get(chunk["chunk_id"], "").split())
            lines.append(f"- `{chunk['chunk_id']}` — {body}")
        lines.append("")

    WORKSHEET_FILE.write_text("\n".join(lines), encoding="utf-8")

    if LABELS_FILE.exists():
        skeleton = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    else:
        skeleton = {
            "criterion": CRITERION,
            "labelled_by": "REPLACE WITH YOUR NAME",
            "labelled_at": "REPLACE WITH THE DATE YOU LABELLED",
            "judge_had_been_run": False,
            "labels": {},
        }
    # Top up slots for newly generated cases without overwriting labels already written.
    added = [case_id for case_id in to_label if case_id not in skeleton["labels"]]
    for case_id in added:
        skeleton["labels"][case_id] = PLACEHOLDER
    skeleton["labels"] = {
        case_id: skeleton["labels"][case_id] for case_id in sorted(skeleton["labels"])
    }
    LABELS_FILE.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")

    filled = sum(1 for verdict in skeleton["labels"].values() if verdict != PLACEHOLDER)
    print(
        f"{LABELS_FILE.name}: {len(skeleton['labels'])} slots, "
        f"{len(added)} added, {filled} already labelled"
    )

    print(f"wrote {WORKSHEET_FILE.name} covering {len(to_label)} case(s)")
    if missing:
        print(f"still ungenerated: {', '.join(missing)}")


if __name__ == "__main__":
    main()
