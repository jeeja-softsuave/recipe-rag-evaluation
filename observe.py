"""The Week 11 production app: the Week 5/6 RAG pipeline, instrumented span by span.

Every request writes one JSON line to logs/app.jsonl with what an on-call engineer needs
to find it again: who asked, when, what kind of question, which prompt version answered,
which chunks were retrieved, what was said, and per-span latency, tokens and cost.

Spans:
  retrieval   hybrid BM25 + vector + RRF. Embeddings run locally (all-MiniLM-L6-v2 via
              ONNX), so this span spends no API tokens and costs $0 in API terms.
  generation  the one model call. Tokens come from the API's usage report.
  tools       citation verification against the index. Deterministic; no model.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb

from assertions import (
    CAVEAT_PATTERN,
    DAIRY_FREE_REQUEST_PATTERN,
    DAIRY_PRODUCT_PATTERN,
    PLANT_SUBSTITUTE_ALLERGENS,
)
from prompts import PROMPTS
from recipe_rag import (
    CHROMA_DIR,
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    REFUSAL_TEXT,
    STRUCTURE_AWARE_COLLECTION,
    TOP_K,
    _retry_delay,
    build_generation_prompt,
    is_rate_limit_error,
    search_hybrid_rrf,
    verify_citations,
)

LOG_DIR = Path(__file__).parent / "logs"
APP_LOG = LOG_DIR / "app.jsonl"
# Stated assumption, as in weeks 7-10: list prices, because the free tier bills nothing.
PRICE_INPUT_PER_1M_USD = 0.30
PRICE_OUTPUT_PER_1M_USD = 2.50
# A daily-quota 429 also says "retry in 31s"; one visible retry covers the per-minute case.
MAX_RATE_LIMIT_ATTEMPTS = 2

# Primary input type, first match wins. Keyword rules, so the label never drifts.
INPUT_TYPES: list[tuple[str, str]] = [
    ("substitution", r"instead|substitut|swap|replac|alternative|in place of|without|can i use"),
    ("allergen", r"allerg|dairy|vegan|gluten|\bnut|lactose|coeliac|celiac|safe for"),
    ("quantity", r"how much|how many|\bgrams?\b|ratio|quantity|half|double|scale"),
    ("process", r"overnight|soak|ferment|refrigerat|fridge|stir|temperature|hours?\b|storage"),
]


def input_type(question: str) -> str:
    """Label a question by what it asks for."""
    lowered = question.lower()
    for label, pattern in INPUT_TYPES:
        if re.search(pattern, lowered):
            return label
    return "other"


def modelled_cost(input_tokens: int, output_tokens: int) -> float:
    """Cost in USD from token counts at the stated list prices."""
    return (input_tokens * PRICE_INPUT_PER_1M_USD
            + output_tokens * PRICE_OUTPUT_PER_1M_USD) / 1_000_000


def _generate(system_prompt: str, user_prompt: str,
              model: str = GEMINI_MODEL) -> tuple[str, int, int]:
    """One model call. Returns the text and the token counts the API reported."""
    from google import genai

    client = genai.Client()
    # The SDK silently retries a 429 four more times, and every retry counts against the
    # daily quota. Retries are handled visibly below instead.
    client.interactions.sdk_configuration.retry_config = None
    for attempt in range(1, MAX_RATE_LIMIT_ATTEMPTS + 1):
        try:
            interaction = client.interactions.create(
                model=model, system_instruction=system_prompt, input=user_prompt,
                generation_config={"thinking_level": GEMINI_THINKING_LEVEL})
        except Exception as error:
            if not is_rate_limit_error(error) or attempt == MAX_RATE_LIMIT_ATTEMPTS:
                raise
            time.sleep(_retry_delay(str(error)))
            continue
        usage = interaction.usage
        return (interaction.output_text or "", usage.total_input_tokens or 0,
                usage.total_output_tokens or 0)
    raise RuntimeError("exhausted Gemini retry attempts")


def swap_flags(question: str, answer: str, refused: bool) -> dict[str, Any]:
    """What a swap answer claims, as structured fields, so it can be found without guessing
    its wording. The same rules as assertions.dairy_free_swap_is_safe."""
    dairy_free = bool(re.search(DAIRY_FREE_REQUEST_PATTERN, question, re.IGNORECASE))
    if refused:
        return {"dairy_free_request": dairy_free, "dairy_products_named": [],
                "plant_swaps_unwarned": []}
    named = sorted({match.group(0).lower()
                    for match in re.finditer(DAIRY_PRODUCT_PATTERN, answer, re.IGNORECASE)})
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    unwarned = [plant for plant, allergen in PLANT_SUBSTITUTE_ALLERGENS.items()
                if re.search(rf"\b{plant}", answer, re.IGNORECASE)
                and not any(re.search(rf"\b(?:{plant}|{allergen})", s, re.I)
                            and re.search(CAVEAT_PATTERN, s, re.I) for s in sentences)]
    return {"dairy_free_request": dairy_free, "dairy_products_named": named,
            "plant_swaps_unwarned": unwarned}


def collection() -> Any:
    """The structure-aware index every week since Week 3 has used."""
    return chromadb.PersistentClient(path=CHROMA_DIR).get_collection(STRUCTURE_AWARE_COLLECTION)


def _span(name: str, started: float, input_tokens: int = 0, output_tokens: int = 0) -> dict[str, Any]:
    """One timed stage of a request."""
    return {
        "span": name,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": modelled_cost(input_tokens, output_tokens),
    }


def answer_observed(question: str, user_id: str, prompt_version: str, *,
                    index: Any = None, at: str | None = None, generate=_generate,
                    model: str = GEMINI_MODEL) -> dict[str, Any]:
    """Answer one question with the given prompt version, and return its log record."""
    index = index or collection()
    request_started = time.perf_counter()

    started = time.perf_counter()
    contexts = search_hybrid_rrf(index, question, TOP_K)
    retrieval = _span("retrieval", started)

    started = time.perf_counter()
    answer, tokens_in, tokens_out = generate(PROMPTS[prompt_version],
                                             build_generation_prompt(question, contexts), model)
    generation = _span("generation", started, tokens_in, tokens_out)

    started = time.perf_counter()
    refused = answer.strip() == REFUSAL_TEXT
    checks = [] if refused else verify_citations(index, answer)
    tools = _span("tools", started)

    timestamp = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    spans = [retrieval, generation, tools]
    return {
        "trace_id": "t-" + hashlib.sha256(f"{timestamp}|{user_id}|{question}".encode()).hexdigest()[:10],
        "timestamp": timestamp,
        "user_id": user_id,
        "input_type": input_type(question),
        "prompt_version": prompt_version,
        "model": model,
        "question": question,
        "answer": answer,
        "refused": refused,
        "context_ids": [c["chunk_id"] for c in contexts],
        "context_scores": [c["score"] for c in contexts],
        "citations_ok": all(check["ok"] for check in checks) if checks else refused,
        "swap_flags": swap_flags(question, answer, refused),
        "spans": spans,
        "latency_ms": round((time.perf_counter() - request_started) * 1000, 1),
        "total_tokens": tokens_in + tokens_out,
        "cost_usd": sum(span["cost_usd"] for span in spans),
    }


def append_log(record: dict[str, Any], path: Path = APP_LOG) -> None:
    """Append one request to the log, one JSON object per line."""
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_log(path: Path = APP_LOG) -> list[dict[str, Any]]:
    """Every logged request, in file order."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
