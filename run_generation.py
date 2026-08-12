"""Answer 3 answerable questions with citations and refuse 3 out-of-corpus ones."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import (
    CHROMA_DIR,
    GEMINI_MODEL,
    STRUCTURE_AWARE_COLLECTION,
    SYSTEM_PROMPT,
    TOP_K,
    answer_with_citations,
    build_generation_prompt,
    search,
)

ANSWERABLE_QUESTIONS = [
    "How much rock salt goes into the idli batter?",
    "How much grated coconut goes into sanna?",
    "At what temperature should the yeast be bloomed for kallappam?",
]
OUT_OF_CORPUS_QUESTIONS = [
    "How many calories are in one idli?",
    "What is the protein and fat macro breakdown of moru?",
    "What is the glycemic index of neeragaram?",
]
PROMPTS_FILE = Path(__file__).parent / "generation_prompts.md"
TRANSCRIPTS_FILE = Path(__file__).parent / "transcripts.md"


def dump_prompts(collection: Any) -> None:
    """Write the exact system and user prompt for every question to a file."""
    blocks = ["# Exact prompts sent for each of the 6 questions", ""]
    blocks.append("## System prompt (identical for all 6)\n")
    blocks.append("```")
    blocks.append(SYSTEM_PROMPT)
    blocks.append("```")
    for label, questions in (
        ("answerable", ANSWERABLE_QUESTIONS),
        ("out_of_corpus", OUT_OF_CORPUS_QUESTIONS),
    ):
        for index, question in enumerate(questions, start=1):
            contexts = search(collection, question, TOP_K)
            blocks.append(f"\n## {label}-{index}: {question}\n")
            blocks.append("```")
            blocks.append(build_generation_prompt(question, contexts))
            blocks.append("```")
    PROMPTS_FILE.write_text("\n".join(blocks), encoding="utf-8")
    print(f"wrote {PROMPTS_FILE.name}")


def main() -> None:
    """Run all 6 questions against the live model and write verified transcripts."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is not set — add it to .env and rerun.")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(STRUCTURE_AWARE_COLLECTION)
    dump_prompts(collection)

    lines = ["# Generation transcripts", ""]
    lines.append(f"**Generator:** Gemini API (live call), model {GEMINI_MODEL}")
    lines.append(f"\n**Collection:** `{STRUCTURE_AWARE_COLLECTION}` · top_k = {TOP_K}")
    lines.append("\n## System prompt (identical for all 6)\n")
    lines.append("```")
    lines.append(SYSTEM_PROMPT)
    lines.append("```")

    all_ok = True
    for label, questions in (
        ("ANSWERABLE", ANSWERABLE_QUESTIONS),
        ("OUT OF CORPUS", OUT_OF_CORPUS_QUESTIONS),
    ):
        for index, question in enumerate(questions, start=1):
            result = answer_with_citations(collection, question, top_k=TOP_K)
            print(
                f"[{label} {index}] refused={result['refused']} "
                f"citations_ok={result['all_citations_ok']}"
            )
            lines.append(f"\n## {label} {index}\n")
            lines.append(f"**Q:** {question}\n")
            lines.append("**Retrieved chunk_ids:** " + ", ".join(
                f"`{c['chunk_id']}`" for c in result["contexts"]
            ))
            lines.append("\n**A (verbatim):**\n")
            lines.append("```")
            lines.append(result["answer"])
            lines.append("```")
            lines.append(f"\n**refused:** {result['refused']}")
            if result["citation_checks"]:
                lines.append("\n| cited chunk_id | exists | claimed values | missing | ok |")
                lines.append("|---|---|---|---|---|")
                for check in result["citation_checks"]:
                    lines.append(
                        f"| `{check['chunk_id']}` | {check['exists']} | "
                        f"{', '.join(check['claimed_values']) or '(none)'} | "
                        f"{', '.join(check['missing_values']) or '(none)'} | {check['ok']} |"
                    )
            lines.append(f"\n**all_citations_ok:** {result['all_citations_ok']}")
            if not result["all_citations_ok"]:
                all_ok = False

    lines.append(f"\n## Overall\n\nEvery transcript passed verification: **{all_ok}**")
    TRANSCRIPTS_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {TRANSCRIPTS_FILE.name} — all verified: {all_ok}")


if __name__ == "__main__":
    main()
