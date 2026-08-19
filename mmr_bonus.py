"""Bonus: MMR over the fused candidate list, scored on hit-rate@3 and top-3 diversity."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import (
    CHROMA_DIR,
    HYBRID_CANDIDATE_DEPTH,
    RRF_K,
    STRUCTURE_AWARE_COLLECTION,
    search,
    search_bm25,
)
from evaluate_retrieval import TOP_K_EVAL, accepted_ids, load_golden_set

LAMBDA_GRID = (0.3, 0.5, 0.7, 0.9)
EPSILON = 1e-9
DIVERSITY_DECIMALS = 4
MEAN_DECIMALS = 2
CHUNK_ID_SEPARATOR = "::"
RESULTS_FILE = Path(__file__).parent / "mmr_bonus.json"


def _embeddings(collection: Any) -> dict[str, list[float]]:
    """Fetch the stored embedding for every chunk, keyed by chunk_id."""
    stored = collection.get(include=["embeddings"])
    return {
        chunk_id: list(vector)
        for chunk_id, vector in zip(stored["ids"], stored["embeddings"])
    }


def _cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot_product = sum(
        left_value * right_value for left_value, right_value in zip(left, right)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot_product / max(left_norm * right_norm, EPSILON)


def fused_candidates(collection: Any, query: str) -> list[tuple[str, float]]:
    """Return (chunk_id, rrf_score) candidates from the same fusion the app ships."""
    fused: dict[str, float] = {}
    for ranking in (
        search(collection, query, HYBRID_CANDIDATE_DEPTH),
        search_bm25(collection, query, HYBRID_CANDIDATE_DEPTH),
    ):
        for hit in ranking:
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (
                RRF_K + hit["rank"]
            )
    return sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))


def mmr_select(
    candidates: list[tuple[str, float]],
    vectors: dict[str, list[float]],
    lambda_value: float,
    top_k: int = TOP_K_EVAL,
) -> list[str]:
    """Greedily pick top_k chunk_ids trading relevance against similarity to those chosen."""
    if not candidates:
        return []
    best_relevance = max(score for _, score in candidates)
    remaining = list(candidates)
    selected: list[str] = []
    while remaining and len(selected) < top_k:
        best_id, best_value = None, float("-inf")
        for chunk_id, relevance in remaining:
            penalty = max(
                (_cosine(vectors[chunk_id], vectors[chosen]) for chosen in selected),
                default=0.0,
            )
            value = lambda_value * (relevance / best_relevance) - (1 - lambda_value) * penalty
            if value > best_value:
                best_id, best_value = chunk_id, value
        selected.append(best_id)
        remaining = [pair for pair in remaining if pair[0] != best_id]
    return selected


def top3_diversity(chunk_ids: list[str], vectors: dict[str, list[float]]) -> float:
    """Mean pairwise cosine distance across the selected chunks: higher means more varied."""
    distances = [
        1.0 - _cosine(vectors[first_id], vectors[second_id])
        for index, first_id in enumerate(chunk_ids)
        for second_id in chunk_ids[index + 1 :]
    ]
    if not distances:
        return 0.0
    return round(statistics.mean(distances), DIVERSITY_DECIMALS)


def main() -> None:
    """Sweep lambda once and report hit-rate@3 alongside top-3 diversity."""
    golden = load_golden_set()
    in_corpus = [item for item in golden if item["gold_chunk_id"] is not None]
    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )
    vectors = _embeddings(collection)
    candidates = {item["id"]: fused_candidates(collection, item["question"]) for item in golden}

    report: dict[str, Any] = {}
    print(f"| selector | hit-rate@{TOP_K_EVAL} | mean top-3 diversity | distinct recipes |")
    print("|---|---|---|---|")
    for lambda_value in (None, *LAMBDA_GRID):
        hits = 0
        diversities: list[float] = []
        distinct_recipe_counts: list[int] = []
        for item in in_corpus:
            pool = candidates[item["id"]]
            if lambda_value is None:
                chosen = [cid for cid, _ in pool[:TOP_K_EVAL]]
            else:
                chosen = mmr_select(pool, vectors, lambda_value)
            if accepted_ids(item) & set(chosen):
                hits += 1
            diversities.append(top3_diversity(chosen, vectors))
            distinct_recipe_counts.append(
                len({cid.split(CHUNK_ID_SEPARATOR)[0] for cid in chosen})
            )
        label = "bm25 + rrf (shipping)" if lambda_value is None else f"MMR lambda={lambda_value}"
        mean_diversity = round(statistics.mean(diversities), DIVERSITY_DECIMALS)
        mean_distinct_recipes = round(
            statistics.mean(distinct_recipe_counts), MEAN_DECIMALS
        )
        report[label] = {
            "hits": hits,
            "total": len(in_corpus),
            "diversity": mean_diversity,
            "distinct_recipes": mean_distinct_recipes,
        }
        print(f"| {label} | {hits}/{len(in_corpus)} | {mean_diversity} | {mean_distinct_recipes} |")

    RESULTS_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    main()
