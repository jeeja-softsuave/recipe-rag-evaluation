"""Pantry-to-Plate: the single entry point for the integrated system.

    python pantry.py ask "can my nut-allergic kid eat kallappam?"   # one question, end to end
    python pantry.py trace t-1a2b3c4d5e6f                            # every span of one request
    python pantry.py serve                                           # the MCP server, for any client
    python pantry.py index                                           # rebuild the capstone index

What runs, in order: the Week 7 agent loop (here with Week 9 MCP discovery) asks the model
which tool to call; tools are discovered at start-up from capstone_config.json, never
hardcoded; search is the Week 3-4 RAG retriever; every request gets ONE random trace id that
travels with every model call and, through MCP's _meta, into every tool call on the server.

PII line (health data): a user's stated allergies are health data. This file never writes
the raw question or any user identifier. It writes a redacted question (health and family
words replaced), a salted hash of the original for de-duplication, the allergen CATEGORIES
the tools were asked about (needed to audit safety, not linked to a person), the answer, and
per-span cost and latency. The trace id is random, so it cannot be recomputed from the text.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from capstone_corpus import build, load_cards, stated_allergens, unsafe_recommendation
from mcp_agent import ToolHub, _function_calls, connect, load_config
from recipe_rag import GEMINI_THINKING_LEVEL, _retry_delay, is_rate_limit_error

PROJECT_DIR = Path(__file__).parent
CONFIG = PROJECT_DIR / "capstone_config.json"
REQUEST_LOG = PROJECT_DIR / "logs" / "capstone.jsonl"
SPAN_LOG = PROJECT_DIR / "logs" / "capstone_spans.jsonl"
PROMPT_VERSION = "c1"
# p1: the model writes the whole answer (the before run, 2026-10-21).
# p2: the host puts the declaration verdict and its citation first (2026-10-22).
# p3: p2 + a swap guard: a recommended swap that contains an allergen the user named is
#     withheld (the closed failure->test loop for after-run s03, trace t-31159cd80f8a).
PIPELINE_VERSION = os.environ.get("PANTRY_PIPELINE", "p3")
VERDICT_LINE = re.compile(r"ALLERGEN_VERDICT:\s*([a-z_]+)")
# The capstone runs on Flash-Lite: Gemini 3.6 Flash (weeks 7-10) was refused by an
# account-level quota cap on most days of capstone week. One model everywhere, so every
# before -> after is comparable. Override with PANTRY_MODEL.
MODEL = os.environ.get("PANTRY_MODEL", "gemini-3.5-flash-lite")
MAX_LAPS = 8
MAX_RATE_LIMIT_ATTEMPTS = 2
OVERLOAD_ATTEMPTS = 4
OVERLOAD_WAIT_SECONDS = 20
# Stated assumption, as in weeks 7-11: list prices; the free tier bills nothing.
PRICE_INPUT_PER_1M_USD = 0.30
PRICE_OUTPUT_PER_1M_USD = 2.50
HASH_SALT = os.environ.get("PANTRY_LOG_SALT", "pantry-capstone")
REDACTIONS = [
    (r"\b(?:my|our|his|her|their)\s+(?:kid|son|daughter|child|children|baby|wife|husband|"
     r"partner|friend|mum|mom|dad|family|guest)s?\b", "[PERSON]"),
    (r"\b(?:allerg\w*|intoleran\w*|coeliac|celiac|anaphyla\w*|epipen)\b", "[HEALTH]"),
]
CITATION = re.compile(r"\[([a-z0-9-]+@[a-z0-9-]+(?:::structure::\d+)?)\]")

SYSTEM_INSTRUCTION = """You answer cooking questions about the publisher's recipe library, using
only the tools provided. Take every recipe fact from a tool result.

Cite every recipe fact in square brackets with the chunk_id or citation the tool returned, for
example [kallappam-batter-02@reformulated-2025::structure::1]. A citation must name the version.

For any allergy or dietary restriction, call check_allergens with every allergen the user
mentions and answer from its verdict; never judge allergen safety from recipe text. When asked to
scale, use scale_recipe and give the times exactly as it returns them. For cooking, reheating or
storing food, call safe_temperature and state the number. If the tools cannot answer, say so
plainly instead of guessing.

If the question involves an allergy, end with one line:
ALLERGEN_VERDICT: unsafe | may_contain | no_declared_allergen | not_checked"""


def is_quota_error(error: BaseException) -> bool:
    """A rate-limit refusal, even when anyio wraps it in nested exception groups."""
    if isinstance(error, BaseExceptionGroup):
        return any(is_quota_error(inner) for inner in error.exceptions)
    return is_rate_limit_error(error) or (error.__cause__ is not None
                                          and is_quota_error(error.__cause__))


SEVERITY = {"unsafe": 2, "may_contain": 1, "no_declared_allergen": 0}
HEADLINE = {"unsafe": "NOT SAFE: contains {hits}",
            "may_contain": "MAY CONTAIN {hits}: not safe for a {hits} allergy without a supplier guarantee",
            "no_declared_allergen": "no declared {asked} (neither contains nor may contain)"}


def declaration_first(answer: str, calls: list[dict[str, Any]]) -> tuple[str, str | None]:
    """Pipeline p2: the host, not the model, states the allergen verdict, FIRST.

    Every successful check_allergens call becomes one line at the top of the answer, worded
    from the declaration field and cited by recipe@version. The verdict line is written from
    the same results, so a model that drops it, or contradicts it, cannot hide either.
    """
    lines, verdicts = [], []
    for call in calls:
        if call["tool"] != "check_allergens" or call["is_error"]:
            continue
        result = json.loads(call["result"])
        if not result.get("checked"):
            continue
        per = result["per_allergen"]
        hits = ", ".join(a for a, v in per.items() if v != "not_declared")
        line = (f"Allergen check, from the declaration field: {result['recipe_id']} "
                f"({result['version']}): " + HEADLINE[result["verdict"]].format(
                    hits=hits, asked=", ".join(per)) + f" [{result['citation']}]")
        if line not in lines:
            lines.append(line)
            verdicts.append(result["verdict"])
    if not lines:
        return answer, (m.group(1) if (m := VERDICT_LINE.search(answer)) else None)
    worst = max(verdicts, key=SEVERITY.__getitem__)
    body = VERDICT_LINE.sub("", answer).strip()
    return "\n".join(lines) + "\n\n" + body + f"\n\nALLERGEN_VERDICT: {worst}", worst


def swap_guard(question: str, answer: str, calls: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Pipeline p3: never let an answer recommend a swap that contains an allergen the user named.

    The allergens come from the question and from every check_allergens call. If a recommended
    swap contains one, the model's prose is withheld and replaced by a statement of the conflict.
    The declaration header and the verdict line, which come from the tools, are kept.
    """
    avoid = stated_allergens(question) | {a for c in calls if c["tool"] == "check_allergens"
                                          for a in (c["arguments"].get("avoid") or [])}
    conflict = unsafe_recommendation(answer, avoid)
    if conflict is None:
        return answer, None
    phrase, allergen, word = conflict
    header = [line for line in answer.splitlines() if line.startswith("Allergen check, from the declaration field")]
    verdict = VERDICT_LINE.search(answer)
    note = (f"I have withheld a suggested swap: '{phrase.replace('*', '').strip()}' contains {allergen}, which you "
            f"asked to avoid. The test kitchen's substitution table records no {allergen}-free "
            f"replacement for this. Treat the recipe as unsuitable unless a supplier confirms one.")
    parts = ["\n".join(header), note, verdict.group(0) if verdict else ""]
    return "\n\n".join(part for part in parts if part), {"withheld": phrase, "allergen": allergen, "word": word}


def redact(text: str) -> str:
    """The question as it may be logged: family and health words replaced."""
    for pattern, replacement in REDACTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def modelled_cost(tokens_in: int, tokens_out: int) -> float:
    """USD at the stated list prices."""
    return (tokens_in * PRICE_INPUT_PER_1M_USD + tokens_out * PRICE_OUTPUT_PER_1M_USD) / 1_000_000


def render_citations(answer: str) -> str:
    """Turn each version-qualified citation into a link to the card file it came from."""
    cards = load_cards()

    def link(match: re.Match) -> str:
        cited = match.group(1)
        card = cards.get(cited.split("::")[0])
        return f"[{cited}]({card['source_file']})" if card else match.group(0)

    return CITATION.sub(link, answer)


def _gemini_step(instruction: str, payload: Any, previous_id: str | None, specs: Any) -> Any:
    """One model call with the discovered tools. SDK retries off; one visible retry."""
    from google import genai

    client = genai.Client()
    client.interactions.sdk_configuration.retry_config = None
    request: dict[str, Any] = {"model": MODEL, "input": payload, "tools": specs,
                               "generation_config": {"thinking_level": GEMINI_THINKING_LEVEL}}
    if previous_id is None:
        request["system_instruction"] = instruction
    else:
        request["previous_interaction_id"] = previous_id
    for attempt in range(1, max(MAX_RATE_LIMIT_ATTEMPTS, OVERLOAD_ATTEMPTS) + 1):
        try:
            return client.interactions.create(**request)
        except Exception as error:
            # A 503 "high demand" is the provider's transient overload, not our quota: wait and
            # retry it a few times rather than lose the run.
            overloaded = "503" in str(error) or "high demand" in str(error)
            limit = OVERLOAD_ATTEMPTS if overloaded else MAX_RATE_LIMIT_ATTEMPTS
            if not (overloaded or is_rate_limit_error(error)) or attempt >= limit:
                raise
            time.sleep(OVERLOAD_WAIT_SECONDS * attempt if overloaded else _retry_delay(str(error)))
    raise RuntimeError("exhausted Gemini retry attempts")


async def _call_tool(hub: ToolHub, name: str, arguments: dict[str, Any],
                     trace_id: str) -> tuple[str | None, bool, str]:
    """Route one call to its server, carrying the trace id in the MCP request's _meta."""
    server = hub.tool_owner.get(name)
    if server is None:
        return None, True, f"no connected server offers a tool named {name}"
    try:
        result = await hub.sessions[server].call_tool(name, arguments, meta={"trace_id": trace_id})
    except Exception as error:
        return server, True, f"server {server} failed: {type(error).__name__}: {error}"
    text = "\n".join(b.text for b in result.content if getattr(b, "type", None) == "text")
    return server, bool(result.is_error), text


async def answer(question: str, generate: Callable[..., Any] = _gemini_step,
                 config_path: Path = CONFIG, log: bool = True) -> dict[str, Any]:
    """Answer one question end to end. Returns the full record, and logs the PII-safe one."""
    trace_id = "t-" + secrets.token_hex(6)
    started = time.perf_counter()
    spans: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    final = ""
    stop = "completed"
    async with connect(load_config(config_path)) as hub:
        specs = hub.function_specs()
        payload: Any = question
        previous: str | None = None
        for lap in range(1, MAX_LAPS + 1):
            lap_started = time.perf_counter()
            interaction = await asyncio.to_thread(generate, SYSTEM_INSTRUCTION, payload, previous, specs)
            usage = getattr(interaction, "usage", None)
            tokens_in = (usage.total_input_tokens or 0) if usage else 0
            tokens_out = (usage.total_output_tokens or 0) if usage else 0
            spans.append({"span": f"model:lap{lap}", "latency_ms": round((time.perf_counter() - lap_started) * 1000, 1),
                          "input_tokens": tokens_in, "output_tokens": tokens_out,
                          "cost_usd": modelled_cost(tokens_in, tokens_out)})
            steps = _function_calls(interaction)
            if not steps:
                final = interaction.output_text or ""
                break
            results = []
            for step in steps:
                arguments = dict(step.arguments or {})
                tool_started = time.perf_counter()
                server, is_error, text = await _call_tool(hub, step.name, arguments, trace_id)
                spans.append({"span": f"tool:{step.name}", "server": server,
                              "latency_ms": round((time.perf_counter() - tool_started) * 1000, 1),
                              "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                              "is_error": is_error})
                calls.append({"lap": lap, "server": server, "tool": step.name,
                              "arguments": arguments, "is_error": is_error, "result": text})
                results.append({"type": "function_result", "call_id": step.id, "name": step.name,
                                "result": {"type": "text", "text": text}, "is_error": is_error})
            payload, previous = results, interaction.id
        else:
            stop = "max_laps"

    guard = None
    if PIPELINE_VERSION in ("p2", "p3"):
        final, verdict = declaration_first(final, calls)
    else:
        verdict = m.group(1) if (m := VERDICT_LINE.search(final)) else None
    if PIPELINE_VERSION == "p3":
        final, guard = swap_guard(question, final, calls)
    record = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_version": PROMPT_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "model": MODEL,
        "question": question,
        "answer": final,
        "allergen_verdict": verdict,
        "swap_guard": guard,
        "citations": CITATION.findall(final),
        "calls": calls,
        "spans": spans,
        "stop": stop,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "total_tokens": sum(s["input_tokens"] + s["output_tokens"] for s in spans),
        "cost_usd": sum(s["cost_usd"] for s in spans),
    }
    if log:
        write_log(record)
    return record


def _as_list(value: Any) -> list[str]:
    """`avoid` is a list for check_allergens and a single string for substitute_ingredient."""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def write_log(record: dict[str, Any]) -> None:
    """Append the PII-safe form of a request: no raw question, no user identifier."""
    categories = sorted({allergen for call in record["calls"]
                         for allergen in _as_list(call["arguments"].get("avoid"))})
    safe = {key: record[key] for key in ("trace_id", "timestamp", "prompt_version",
                                         "pipeline_version", "swap_guard", "model",
                                         "answer", "allergen_verdict", "citations", "spans",
                                         "stop", "latency_ms", "total_tokens", "cost_usd")}
    safe.update({
        "question_redacted": redact(record["question"]),
        "question_hash": hashlib.sha256((HASH_SALT + record["question"]).encode()).hexdigest()[:16],
        "allergen_categories": categories,
        "tool_calls": [{"tool": c["tool"], "server": c["server"], "is_error": c["is_error"],
                        "recipe_id": c["arguments"].get("recipe_id")} for c in record["calls"]],
    })
    REQUEST_LOG.parent.mkdir(exist_ok=True)
    with REQUEST_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, ensure_ascii=False) + "\n")


def show_trace(trace_id: str) -> None:
    """Every span of one request: the agent's model and tool spans, then the server's own."""
    def lines(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    request = next((r for r in lines(REQUEST_LOG) if r["trace_id"] == trace_id), None)
    server = [s for s in lines(SPAN_LOG) if s.get("trace_id") == trace_id]
    if request is None:
        print(f"no request with trace id {trace_id}")
        return
    print(f"trace {trace_id}  prompt {request['prompt_version']}  {request['model']}")
    print(f"question (redacted): {request['question_redacted']}")
    print(f"{'span':<34}{'latency ms':>12}{'tokens':>9}{'cost usd':>12}")
    for span in request["spans"]:
        print(f"{span['span']:<34}{span['latency_ms']:>12}{span['input_tokens'] + span['output_tokens']:>9}"
              f"{span['cost_usd']:>12.6f}")
    for span in server:
        print(f"  server {span['span']:<25}{span['latency_ms']:>12}{0:>9}{0:>12.6f}")
    print(f"{'total':<34}{request['latency_ms']:>12}{request['total_tokens']:>9}{request['cost_usd']:>12.6f}")
    print(f"citations: {request['citations']}")


def main() -> None:
    """ask | trace | serve | index"""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="answer one question end to end")
    ask.add_argument("question")
    ask.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot")
    trace = sub.add_parser("trace", help="print every span of one request")
    trace.add_argument("trace_id")
    sub.add_parser("serve", help="run the pantry MCP server on stdio, for any MCP client")
    sub.add_parser("index", help="rebuild the capstone index")
    args = parser.parse_args()

    if args.command == "ask":
        name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
        os.environ["GEMINI_API_KEY"] = os.environ[name]
        try:
            record = asyncio.run(answer(args.question))
        except Exception as error:
            if not is_quota_error(error):
                raise
            raise SystemExit(f"model quota refused on key {args.key} ({MODEL}); "
                             "nothing was logged. Try another --key, or later.")
        for call in record["calls"]:
            print(f"  [{call['server']}] {call['tool']}({json.dumps(call['arguments'])})"
                  f"{' ERROR' if call['is_error'] else ''}")
        print("\n" + render_citations(record["answer"]))
        print(f"\ntrace {record['trace_id']}  {record['latency_ms'] / 1000:.1f}s  "
              f"{record['total_tokens']} tokens  ${record['cost_usd']:.6f}")
    elif args.command == "trace":
        show_trace(args.trace_id)
    elif args.command == "serve":
        from pantry_server import server
        server.run()
    elif args.command == "index":
        print(f"{build()} chunks indexed")


if __name__ == "__main__":
    main()
