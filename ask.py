"""Interactive console: ask a question, get an answer cited to the recipe cards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import (
    BASELINE_COLLECTION,
    CHROMA_DIR,
    STRUCTURE_AWARE_COLLECTION,
    TOP_K,
    answer_with_citations,
    is_rate_limit_error,
    search,
)

QUESTIONS_FILE = Path(__file__).parent / "eval_questions.json"
ANSWER_KEYS_FILE = Path(__file__).parent / "answer_keys.json"
CARDS_SUBDIR = "data/recipe_cards"
RETRIEVAL_ONLY_FLAG = "!r"
FRESH_FLAG = "!fresh"
CACHE_FILE = Path(__file__).parent / "answer_cache.json"
BOM = "﻿"
PROMPT = "\nask a recipe question > "
MENU_HINT = (
    "Type a question, or 1-8 for one of the known-answer questions above.\n"
    f"A new answer costs 1 API call; repeats replay from cache for free.\n"
    f"Add ' {RETRIEVAL_ONLY_FLAG}' to compare both chunkers without answering, or\n"
    f"' {FRESH_FLAG}' to force a new API call. 'q' quits."
)


def load_questions() -> list[dict[str, Any]]:
    """Load the 8 eval questions and attach their known-correct value."""
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    keys = json.loads(ANSWER_KEYS_FILE.read_text(encoding="utf-8"))
    for question in questions:
        question["known_value"] = keys[question["id"]]["value"]
    return questions


def print_menu(questions: list[dict[str, Any]]) -> None:
    """List the known-answer questions so they can be picked by number."""
    print("\nKnown-answer questions:")
    for index, question in enumerate(questions, start=1):
        print(f"  {index}. {question['question']}")
    print(f"\n{MENU_HINT}")


def load_cache() -> dict[str, str]:
    """Load previously generated answers so repeat questions cost no API call."""
    if not CACHE_FILE.exists():
        return {}
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))


def show_answer(
    collection: Any, query: str, expected: dict[str, Any] | None, force_fresh: bool = False
) -> bool:
    """Answer one question from the cards and print its sources; False if quota is spent."""
    cache = load_cache()
    cached = None if force_fresh else cache.get(query)
    try:
        if cached is not None:
            result = answer_with_citations(collection, query, lambda _s, _u: cached, TOP_K)
        else:
            result = answer_with_citations(collection, query, top_k=TOP_K)
            cache[query] = result["answer"]
            CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as error:
        if not is_rate_limit_error(error):
            raise
        print("\n  The Gemini free-tier quota is spent, so no answer can be generated.")
        print("  Showing retrieval instead — it is free and runs locally.")
        return False

    origin = "replayed from cache" if cached is not None else "live API call"
    print(f"\n  {result['answer']}")
    print(f"  [{origin}; citations re-verified locally either way]")
    if result["refused"]:
        print("\n  (That is not in these recipe cards, so the app refused rather than guess.)")
        return True

    source_of = {c["chunk_id"]: c["source_file"] for c in result["contexts"]}
    print("\n  sources")
    for check in result["citation_checks"]:
        card = source_of.get(check["chunk_id"], "NOT IN RETRIEVED CONTEXT")
        flag = "ok " if check["ok"] else "BAD"
        print(f"   {flag} {CARDS_SUBDIR}/{card}   [{check['chunk_id']}]")
        if not check["ok"]:
            print(f"        claimed {check['claimed_values']} not found in that chunk")
    print(f"   every citation checked out: {result['all_citations_ok']}")

    if expected is not None:
        matched = expected["value"].lower() in result["answer"].lower()
        print(
            f"\n  known answer: {expected['value']} "
            f"({expected['recipe_id']} / {expected['section']})  ->  "
            f"{'MATCHED' if matched else 'DID NOT MATCH'}"
        )
    return True


def show_retrieval(
    collections: dict[str, Any], query: str, expected: dict[str, Any] | None
) -> None:
    """Print the top-k list from each collection, marking hits against the known answer."""
    for label, collection in collections.items():
        hits = search(collection, query, TOP_K)
        verdict = ""
        if expected is not None:
            ranks = [h["rank"] for h in hits if h["recipe_id"] == expected["recipe_id"]]
            verdict = f"  HIT (first correct at rank {ranks[0]})" if ranks else "  MISS"
        print(f"\n  {label}{verdict}")
        for hit in hits:
            mark = " "
            if expected is not None and hit["recipe_id"] == expected["recipe_id"]:
                mark = "*"
            value = ""
            if expected is not None and expected["value"] in hit["text"]:
                value = f"  <- contains {expected['value']}"
            print(
                f"   {mark} {hit['rank']}. {hit['chunk_id']:<44} "
                f"{hit['section']:<14} {hit['score']}{value}"
            )
            print(f"        source: {CARDS_SUBDIR}/{hit['source_file']}")


def main() -> None:
    """Run the interactive loop until the user quits."""
    questions = load_questions()
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collections = {
        "baseline       ": client.get_collection(BASELINE_COLLECTION),
        "structure_aware": client.get_collection(STRUCTURE_AWARE_COLLECTION),
    }
    structure_collection = collections["structure_aware"]
    print_menu(questions)

    while True:
        try:
            raw = input(PROMPT).lstrip(BOM).strip()
        except EOFError:
            break
        if not raw or raw.lower() in {"q", "quit", "exit"}:
            break

        retrieval_only = RETRIEVAL_ONLY_FLAG in raw
        force_fresh = FRESH_FLAG in raw
        query = raw.replace(RETRIEVAL_ONLY_FLAG, "").replace(FRESH_FLAG, "").strip()
        expected: dict[str, Any] | None = None

        if query.isdigit() and 1 <= int(query) <= len(questions):
            question = questions[int(query) - 1]
            query = question["question"]
            expected = {
                "recipe_id": question["expected_recipe_id"],
                "section": question["expected_section"],
                "value": question["known_value"],
            }
        print(f"\nQ: {query}")

        if retrieval_only:
            show_retrieval(collections, query, expected)
        elif not show_answer(structure_collection, query, expected, force_fresh):
            show_retrieval(collections, query, expected)

    print("bye")


if __name__ == "__main__":
    main()
