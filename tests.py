"""Guards for the two claims the write-up makes: ingest validation and citation checking."""

from __future__ import annotations

import chromadb

from recipe_rag import (
    CHROMA_DIR,
    STRUCTURE_AWARE_COLLECTION,
    build_index,
    chunk_structure_aware,
    load_recipe_cards,
    verify_citations,
)

GUARD_COLLECTION = "recipes_guard_test"
CITATION_CASES = [
    ("correct value", "The idli batter takes 16g of rock salt [idli-batter-05::structure::0]."),
    ("wrong value", "The idli batter takes 35g of rock salt [idli-batter-05::structure::0]."),
    ("right value, wrong chunk", "The idli batter takes 16g of rock salt [moru-04::structure::0]."),
    ("invented chunk id", "The idli batter takes 16g of rock salt [does-not-exist::structure::99]."),
    ("correct percent", "The kallappam batter is 84% hydration [kallappam-batter-02::structure::0]."),
    ("wrong percent", "The kallappam batter is 62% hydration [kallappam-batter-02::structure::0]."),
    ("decimal percent", "The salt is 2.3% of the rice [kuzhi-paniyaram-batter-01::structure::0]."),
    ("wrong ratio", "The rice to dal ratio is 1:9 [kuzhi-paniyaram-batter-01::structure::1]."),
]


def test_source_file_guard() -> bool:
    """A chunk with an empty source_file must be refused before upsert."""
    card = load_recipe_cards()[0]
    chunks = chunk_structure_aware(card)
    chunks[2]["metadata"]["source_file"] = "   "
    try:
        build_index(GUARD_COLLECTION, chunks)
    except ValueError as error:
        print(f"PASS  empty source_file refused -> {error}")
        return True
    print("FAIL  empty source_file was accepted")
    return False


def test_citation_checks() -> bool:
    """Wrong values, wrong chunks and invented chunk ids must all fail verification."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(STRUCTURE_AWARE_COLLECTION)
    expected_ok = {"correct value", "correct percent", "decimal percent"}
    passed = True
    for label, answer in CITATION_CASES:
        for check in verify_citations(collection, answer):
            should_pass = label in expected_ok
            verdict = "PASS " if check["ok"] == should_pass else "FAIL "
            if check["ok"] != should_pass:
                passed = False
            print(
                f"{verdict} {label:<26} exists={check['exists']} "
                f"claimed={check['claimed_values']} missing={check['missing_values']} "
                f"ok={check['ok']}"
            )
    return passed


def main() -> None:
    """Run both guards and exit non-zero if either fails."""
    results = [test_source_file_guard(), test_citation_checks()]
    print(f"\nall guards passed: {all(results)}")
    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
