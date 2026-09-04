"""Label the substitution cases one keystroke at a time, saving after every answer."""

from __future__ import annotations

import json
import textwrap

import chromadb

from make_labels import CRITERION, LABELS_FILE, PLACEHOLDER, chunk_texts
from recipe_rag import CHROMA_DIR, STRUCTURE_AWARE_COLLECTION
from run_substitutions import load_outputs

WRAP = 96
MENU = "  [p] PASS   [f] FAIL   [s] skip   [q] save and quit  > "


def wrap(text: str, indent: str = "  ") -> str:
    """Wrap one blob of text so long recipe chunks stay readable in a terminal."""
    return textwrap.fill(
        " ".join(text.split()),
        width=WRAP,
        initial_indent=indent,
        subsequent_indent=indent + "  ",
    )


def main() -> None:
    """Walk the unlabelled cases, writing each verdict straight to labels_25.json."""
    stored = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    outputs = load_outputs()
    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )

    pending = [c for c, v in sorted(stored["labels"].items()) if v == PLACEHOLDER]
    if not pending:
        print("every slot is already labelled - nothing to do")
        return

    print("=" * WRAP)
    print("THE ONLY QUESTION YOU ARE ANSWERING:")
    print(wrap(CRITERION))
    print("\nNot wording, not tone, not completeness, not citation format, not whether")
    print("numbers parse. Those are checked by assertions, not by you.")
    print("=" * WRAP)
    print(f"\n{len(pending)} case(s) to label. Saved after every keystroke, so you can stop.\n")

    for number, case_id in enumerate(pending, start=1):
        output = outputs[case_id]
        texts = chunk_texts(collection, [c["chunk_id"] for c in output["retrieved"]])
        print("-" * WRAP)
        print(f"{case_id}   ({number} of {len(pending)})")
        print("\nASKED")
        print(wrap(output["request"]))
        print("\nTHE APP ANSWERED")
        print(wrap(output["answer"].strip()))
        print("\nCONTEXT IT WAS GIVEN (the only source of truth)")
        for chunk in output["retrieved"]:
            print(wrap(f"[{chunk['chunk_id']}] {texts.get(chunk['chunk_id'], '')}"))
        print()

        while True:
            choice = input(MENU).strip().lower()
            if choice in {"p", "f", "s", "q"}:
                break
            print("  type p, f, s or q")

        if choice == "q":
            break
        if choice == "s":
            print("  skipped\n")
            continue
        stored["labels"][case_id] = "PASS" if choice == "p" else "FAIL"
        LABELS_FILE.write_text(json.dumps(stored, indent=2), encoding="utf-8")
        print(f"  recorded {stored['labels'][case_id]}\n")

    remaining = [c for c, v in stored["labels"].items() if v == PLACEHOLDER]
    done = len(stored["labels"]) - len(remaining)
    print("-" * WRAP)
    print(f"{done}/{len(stored['labels'])} labelled")
    if remaining:
        print(f"still unlabelled: {', '.join(sorted(remaining))}")
        print("rerun: python label.py")
    else:
        print("\nNow fill in labelled_by and labelled_at, then COMMIT labels_25.json")
        print("before running the judge. run_judge.py will refuse until you do.")


if __name__ == "__main__":
    main()
