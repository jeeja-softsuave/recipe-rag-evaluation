"""Sealed planter for the Week 11 drill. Run it, and do not read logs/app.jsonl afterwards
until the drill clock starts.

Plants ONE bad substitution answer - a dairy item recommended as dairy-free - into
logs/app.jsonl, in the same schema the app writes, at a random v2-era time, from a random
user, in time order. The choice comes from the OS's secret randomness and is never printed
or stored; the only output is a line count.

What is real in the planted line: retrieval (run for real on the planted question), the
citation check (run for real on the planted answer), the schema and the trace id rule.
What is copied: generation latency and tokens, from a randomly chosen real v2 line, so
the planted line is not a cost outlier. What is synthetic: the answer itself - that is the
plant.

LIMIT, stated in drill.md: the author of this script also runs the drill, so the pools
below are known to the searcher. A colleague-planted line would be a stronger test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path

from observe import (
    APP_LOG,
    swap_flags,
    _span,
    collection,
    input_type,
    load_log,
    modelled_cost,
)
from recipe_rag import TOP_K, search_hybrid_rrf, verify_citations

QUESTIONS = [
    "need moru without dairy for my son, what goes in place of the curd",
    "can moru be made dairy free, what do i swap",
    "whats a non dairy replacement for the curd in moru",
    "my wife has cut out dairy, how do i still make moru",
    "dairy-free alternative to curd for spiced buttermilk",
    "swap for curd in moru if we avoid milk products",
]
# Round 2 (bonus): worded so that round 1's search - a regex for "dairy-free" - misses it.
QUESTIONS_ROUND_2 = [
    "my son has a milk allergy, what can he have instead of curd in moru",
    "cow milk allergy in the family, what replaces the curd in moru",
    "can i make moru safe for a milk allergic kid",
    "milk protein allergy, what goes in moru instead of curd",
]
BAD_SWAPS_ROUND_2 = [
    ("ghee whisked into water", "ghee has the milk proteins cooked out, so it is safe for a milk allergy"),
    ("goat's milk curd", "goat's milk curd is fine for anyone allergic to cow's milk"),
    ("paneer whey", "strained paneer whey has no milk protein left in it"),
    ("cultured butter thinned with water", "the culture breaks down the milk protein that causes the allergy"),
]
BAD_SWAPS = [
    ("lactose-free curd", "lactose-free curd is dairy-free, so it keeps the same sour taste"),
    ("ghee whisked into water", "ghee is pure fat with the milk solids removed, so it counts as dairy-free"),
    ("goat's milk yoghurt", "goat's milk yoghurt is dairy-free and ferments the same way"),
    ("hung curd made from A2 milk", "A2 milk is dairy-free for most people"),
    ("paneer whey", "the whey left after making paneer is dairy-free and pleasantly sour"),
]


def main() -> None:
    """Plant one line and report only the new line count."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default=str(APP_LOG))
    parser.add_argument("--round", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    rng = random.Random(secrets.randbits(128))
    lines = load_log(Path(args.log))
    v2_lines = [line for line in lines if line["prompt_version"] == "v2"]
    if not v2_lines:
        raise SystemExit("no v2 traffic to plant among - run simulate_week.py first")

    question = rng.choice(QUESTIONS if args.round == 1 else QUESTIONS_ROUND_2)
    swap, claim = rng.choice(BAD_SWAPS if args.round == 1 else BAD_SWAPS_ROUND_2)
    donor = rng.choice(v2_lines)
    first = datetime.fromisoformat(min(line["timestamp"] for line in v2_lines))
    last = datetime.fromisoformat(max(line["timestamp"] for line in v2_lines))
    at = first + timedelta(seconds=rng.uniform(0, (last - first).total_seconds()))
    timestamp = at.isoformat(timespec="seconds")
    user_id = rng.choice(sorted({line["user_id"] for line in lines}))

    index = collection()
    started = time.perf_counter()
    contexts = search_hybrid_rrf(index, question, TOP_K)
    retrieval = _span("retrieval", started)
    cited = contexts[0]["chunk_id"]
    if args.round == 1:
        answer = (f"Moru uses thick sour curd [{cited}]. For a dairy-free version, use {swap} "
                  f"instead; {claim} [general].")
    else:
        answer = (f"Moru is made with thick sour curd [{cited}]. You can use {swap} in its "
                  f"place; {claim} [general].")
    generation = dict(next(span for span in donor["spans"] if span["span"] == "generation"))
    generation["cost_usd"] = modelled_cost(generation["input_tokens"], generation["output_tokens"])
    started = time.perf_counter()
    checks = verify_citations(index, answer)
    tools = _span("tools", started)
    spans = [retrieval, generation, tools]

    record = {
        "trace_id": "t-" + hashlib.sha256(f"{timestamp}|{user_id}|{question}".encode()).hexdigest()[:10],
        "timestamp": timestamp, "user_id": user_id, "input_type": input_type(question),
        "prompt_version": "v2", "model": donor["model"], "question": question, "answer": answer,
        "refused": False, "context_ids": [c["chunk_id"] for c in contexts],
        "context_scores": [c["score"] for c in contexts],
        "citations_ok": all(check["ok"] for check in checks) if checks else False,
        "swap_flags": swap_flags(question, answer, False),
        "spans": spans, "latency_ms": round(sum(span["latency_ms"] for span in spans), 1),
        "total_tokens": generation["input_tokens"] + generation["output_tokens"],
        "cost_usd": sum(span["cost_usd"] for span in spans),
    }
    merged = sorted([*lines, record], key=lambda line: line["timestamp"])
    with open(args.log, "w", encoding="utf-8") as handle:
        for line in merged:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"planted 1 line; log now has {len(merged)} lines")


if __name__ == "__main__":
    main()
