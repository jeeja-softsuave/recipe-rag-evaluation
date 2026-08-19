"""Answer the bonus question from each collection and verify both answers."""

from __future__ import annotations

from pathlib import Path

import chromadb

from recipe_rag import (
    BASELINE_COLLECTION,
    CHROMA_DIR,
    STRUCTURE_AWARE_COLLECTION,
    TOP_K,
    _gemini_generate,
    answer_with_citations,
)

BONUS_QUESTIONS = (
    "How much grated coconut goes into sanna?",
    "How do I fill the moulds and steam sanna?",
)
BONUS_COLLECTIONS = (BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION)
# A method-only detail: the moulds must be filled three-quarters full because the
# cakes climb. It appears in no ingredient chunk, so it tests answer completeness.
CAVEAT_PHRASE = "three-quarters"
BONUS_ANSWERS_FILE = Path(__file__).parent / "bonus_answers.md"


def main() -> None:
    """Generate and verify the bonus answer from each collection with a live model."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    lines = ["# Bonus: same questions, both chunkers, live model", ""]
    for question in BONUS_QUESTIONS:
        lines.append(f"\n## Q: {question}\n")
        for name in BONUS_COLLECTIONS:
            collection = client.get_collection(name)
            result = answer_with_citations(collection, question, _gemini_generate, TOP_K)
            answer_caveat = CAVEAT_PHRASE in result["answer"].lower()
            context_caveat = any(
                CAVEAT_PHRASE in chunk["text"].lower() for chunk in result["contexts"]
            )
            print(
                f"[{name}] {question[:40]!r}... citations_ok={result['all_citations_ok']} "
                f"caveat_retrieved={context_caveat} caveat_in_answer={answer_caveat}"
            )
            lines.append(f"\n### {name}\n")
            lines.append("**Retrieved:** " + ", ".join(
                f"`{context['chunk_id']}`" for context in result["contexts"]
            ))
            lines.append(
                f"\n**caveat retrieved:** {context_caveat} · "
                f"**present in answer:** {answer_caveat}"
            )
            lines.append("\n**Answer:**\n")
            lines.append("```")
            lines.append(result["answer"])
            lines.append("```")
            lines.append("\n| cited chunk_id | exists | claimed | missing | ok |")
            lines.append("|---|---|---|---|---|")
            for check in result["citation_checks"]:
                lines.append(
                    f"| `{check['chunk_id']}` | {check['exists']} | "
                    f"{', '.join(check['claimed_values']) or '(none)'} | "
                    f"{', '.join(check['missing_values']) or '(none)'} | {check['ok']} |"
                )
            lines.append(f"\n**all_citations_ok:** {result['all_citations_ok']}")
    BONUS_ANSWERS_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {BONUS_ANSWERS_FILE.name}")


if __name__ == "__main__":
    main()
