"""Write one replayable trace per answered question, and replay a trace from itself."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from recipe_rag import (
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    TOP_K,
    _gemini_generate,
    answer_with_citations,
    build_generation_prompt,
    search_hybrid_rrf,
    verify_citations,
)

TRACES_FILE = Path(__file__).parent / "traces.jsonl"
TRACE_ID_LENGTH = 10
RETRIEVER_NAME = "search_hybrid_rrf"


def new_trace_id(question: str, timestamp: str) -> str:
    """Derive a short, stable trace id from the question and its timestamp."""
    digest = hashlib.sha256(f"{timestamp}|{question}".encode("utf-8")).hexdigest()
    return f"t-{digest[:TRACE_ID_LENGTH]}"


def build_trace(question: str, result: dict[str, Any], source: str) -> dict[str, Any]:
    """Assemble everything needed to replay this answer without the index."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "trace_id": new_trace_id(question, timestamp),
        "timestamp": timestamp,
        "source": source,
        "question": question,
        "prompt_version": PROMPT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": result["user_prompt"],
        "retriever": RETRIEVER_NAME,
        "top_k": TOP_K,
        "retrieved": [
            {
                "rank": context["rank"],
                "chunk_id": context["chunk_id"],
                "score": context["score"],
                "section": context["section"],
                "source_file": context["source_file"],
                "text": context["text"],
            }
            for context in result["contexts"]
        ],
        "model": GEMINI_MODEL,
        "params": {"thinking_level": GEMINI_THINKING_LEVEL},
        "raw_output": result["answer"],
        "refused": result["refused"],
        "citation_checks": result["citation_checks"],
        "all_citations_ok": result["all_citations_ok"],
    }


def append_trace(trace: dict[str, Any], path: Path = TRACES_FILE) -> None:
    """Append one trace as a single JSON line."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(trace) + "\n")


def load_traces(path: Path = TRACES_FILE) -> list[dict[str, Any]]:
    """Load every trace from the trace file."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def answer_and_trace(
    collection: Any, question: str, source: str, path: Path = TRACES_FILE
) -> dict[str, Any]:
    """Answer a question normally and record a replayable trace of it."""
    result = answer_with_citations(
        collection, question, top_k=TOP_K, retriever=search_hybrid_rrf
    )
    trace = build_trace(question, result, source)
    append_trace(trace, path)
    return trace


def replay_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Re-run a trace using only what the trace itself stored, with no retrieval."""
    replayed_output = _gemini_generate(trace["system_prompt"], trace["user_prompt"])
    return {
        "trace_id": trace["trace_id"],
        "original_output": trace["raw_output"],
        "replayed_output": replayed_output,
        "identical": replayed_output.strip() == trace["raw_output"].strip(),
        "prompt_rebuilt_from_trace": trace["user_prompt"],
        "cited_chunks_present_in_trace": sorted(
            {chunk["chunk_id"] for chunk in trace["retrieved"]}
        ),
    }


def rebuild_prompt_from_retrieved(trace: dict[str, Any]) -> str:
    """Rebuild the user prompt from the trace's retrieved chunks, to prove it round-trips."""
    contexts = [
        {"chunk_id": chunk["chunk_id"], "text": chunk["text"]}
        for chunk in trace["retrieved"]
    ]
    return build_generation_prompt(trace["question"], contexts)


def recheck_citations(collection: Any, trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-verify a trace's citations against the live index."""
    return verify_citations(collection, trace["raw_output"])
