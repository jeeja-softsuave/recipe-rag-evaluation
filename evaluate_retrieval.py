"""Measure hit-rate@3 and p50 latency over the golden set, with an inspection view."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import chromadb

from recipe_rag import (
    CHROMA_DIR,
    RRF_K,
    STRUCTURE_AWARE_COLLECTION,
    search,
    search_bm25,
    search_hybrid_rrf,
)

GOLDEN_SET_FILE = Path(__file__).parent / "golden_set.jsonl"
RESULTS_FILE = Path(__file__).parent / "retrieval_eval.json"
TOP_K_EVAL = 3
INSPECT_CHARS = 100
WARMUP_QUERY = "warm up the embedder so latency is not first-call model load"
LATENCY_REPEATS = 5
MS_PER_SECOND = 1000.0
LATENCY_DECIMALS = 1

Retriever = Callable[[Any, str, int], list[dict[str, Any]]]


def load_golden_set(path: Path = GOLDEN_SET_FILE) -> list[dict[str, Any]]:
    """Load the golden set, one JSON object per line."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def accepted_ids(item: dict[str, Any]) -> set[str]:
    """Return every chunk_id that counts as correct for this question."""
    if item["gold_chunk_id"] is None:
        return set()
    return {item["gold_chunk_id"], *item["also_acceptable"]}


def evaluate(
    collection: Any,
    golden: list[dict[str, Any]],
    retriever: Retriever,
    top_k: int = TOP_K_EVAL,
) -> dict[str, Any]:
    """Run every golden question and record hit@k, gold rank and per-query latency."""
    rows: list[dict[str, Any]] = []
    for item in golden:
        started = time.perf_counter()
        hits = retriever(collection, item["question"], top_k)
        elapsed_ms = (time.perf_counter() - started) * MS_PER_SECOND
        accepted = accepted_ids(item)
        ranked = [hit["chunk_id"] for hit in hits]
        gold_rank = next(
            (index for index, cid in enumerate(ranked, start=1) if cid in accepted), None
        )
        # A not-in-corpus question is answered correctly by retrieving nothing useful,
        # so it is scored separately rather than counted as a hit or a miss.
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "gold_chunk_id": item["gold_chunk_id"],
                "exact_token": item["exact_token"],
                "in_corpus": item["gold_chunk_id"] is not None,
                "hit": gold_rank is not None,
                "gold_rank": gold_rank,
                "top_ids": ranked,
                "results": hits,
                "latency_ms": round(elapsed_ms, LATENCY_DECIMALS),
            }
        )
    in_corpus = [row for row in rows if row["in_corpus"]]
    return {
        "rows": rows,
        "hits": sum(1 for row in in_corpus if row["hit"]),
        "total": len(in_corpus),
        "p50_ms": round(
            statistics.median(row["latency_ms"] for row in rows), LATENCY_DECIMALS
        ),
    }


def print_scorecard(label: str, result: dict[str, Any]) -> None:
    """Print the per-question record and the headline numbers."""
    print(f"\n=== {label} · hit-rate@{TOP_K_EVAL} ===")
    print("| id | exact token | gold chunk | hit@3 | gold rank | latency ms |")
    print("|---|---|---|---|---|---|")
    for row in result["rows"]:
        gold = row["gold_chunk_id"] or "(not in corpus)"
        rank = row["gold_rank"] if row["gold_rank"] else "-"
        hit = "-" if not row["in_corpus"] else str(row["hit"]).lower()
        print(
            f"| {row['id']} | {row['exact_token'] or '-'} | {gold} | "
            f"{hit} | {rank} | {row['latency_ms']} |"
        )
    print(
        f"\n{label}: hit-rate@{TOP_K_EVAL} = {result['hits']}/{result['total']} "
        f"in-corpus questions · p50 latency {result['p50_ms']} ms"
    )


def print_inspection(result: dict[str, Any]) -> None:
    """Show the top-k actually returned for every miss, as failure-label evidence."""
    misses = [row for row in result["rows"] if row["in_corpus"] and not row["hit"]]
    print(f"\n=== inspection view · {len(misses)} miss(es) ===")
    for row in misses:
        print(f"\n{row['id']}  {row['question']!r}")
        print(f"  gold chunk never returned: {row['gold_chunk_id']}")
        for hit in row["results"]:
            preview = " ".join(hit["text"].split())[:INSPECT_CHARS]
            print(f"   {hit['rank']}. {hit['chunk_id']:<44} {hit['score']}  {preview}")


def measure_latency(
    collection: Any,
    golden: list[dict[str, Any]],
    retrievers: dict[str, Retriever],
    repeats: int = LATENCY_REPEATS,
) -> dict[str, float]:
    """Time each retriever interleaved per question, so machine drift cannot favour one."""
    samples: dict[str, list[float]] = {name: [] for name in retrievers}
    for _ in range(repeats):
        for item in golden:
            for name, retriever in retrievers.items():
                started = time.perf_counter()
                retriever(collection, item["question"], TOP_K_EVAL)
                samples[name].append((time.perf_counter() - started) * MS_PER_SECOND)
    return {
        name: round(statistics.median(values), LATENCY_DECIMALS)
        for name, values in samples.items()
    }


def print_delta(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Print the per-question fixed / unfixed table and the headline before -> after."""
    print("\n=== per-question: what the one change did ===")
    print("| id | exact token | before hit@3 | after hit@3 | verdict |")
    print("|---|---|---|---|---|")
    for row_before, row_after in zip(before["rows"], after["rows"]):
        if not row_before["in_corpus"]:
            verdict = "not-in-corpus, excluded"
        elif row_before["hit"] and row_after["hit"]:
            verdict = "already passing, untouched"
        elif not row_before["hit"] and row_after["hit"]:
            verdict = "FIXED"
        elif row_before["hit"] and not row_after["hit"]:
            verdict = "REGRESSED"
        else:
            verdict = "still broken"
        before_hit = "-" if not row_before["in_corpus"] else str(row_before["hit"]).lower()
        after_hit = "-" if not row_after["in_corpus"] else str(row_after["hit"]).lower()
        print(
            f"| {row_before['id']} | {row_before['exact_token'] or '-'} | "
            f"{before_hit} | {after_hit} | {verdict} |"
        )
    print("\n=== headline ===")
    print("| metric | before | after |")
    print("|---|---|---|")
    print(f"| hit-rate@{TOP_K_EVAL} | {before['hits']}/{before['total']} | "
          f"{after['hits']}/{after['total']} |")
    print(f"| p50 latency per query | {before['p50_ms']} ms | {after['p50_ms']} ms |")


def main() -> None:
    """Measure the dense baseline, then the one retrieval change, on the same questions."""
    golden = load_golden_set()
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(STRUCTURE_AWARE_COLLECTION)

    # Warm the embedder and the BM25 corpus cache so latency measures steady state.
    search(collection, WARMUP_QUERY, TOP_K_EVAL)
    search_bm25(collection, WARMUP_QUERY, TOP_K_EVAL)

    baseline = evaluate(collection, golden, search)
    print_scorecard("BASELINE dense-only", baseline)
    print_inspection(baseline)

    hybrid = evaluate(collection, golden, search_hybrid_rrf)
    print_scorecard(f"AFTER BM25 + RRF (k={RRF_K})", hybrid)
    print_inspection(hybrid)

    print_delta(baseline, hybrid)

    # A single sequential pass timed each retriever at a different moment, so drift on a
    # busy machine showed up as a fake latency penalty. Interleave and repeat instead.
    latency = measure_latency(
        collection,
        golden,
        {"dense only": search, "bm25 only": search_bm25, "bm25 + rrf": search_hybrid_rrf},
    )
    print(f"\n=== p50 latency, interleaved, {LATENCY_REPEATS} repeats per question ===")
    print("| retriever | p50 ms |")
    print("|---|---|")
    for name, value in latency.items():
        print(f"| {name} | {value} |")

    RESULTS_FILE.write_text(
        json.dumps(
            {"baseline": baseline, "hybrid_rrf": hybrid, "latency_p50_ms": latency}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    main()
