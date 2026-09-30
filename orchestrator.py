"""The Week 10 kitchen squad: an orchestrator, two narrow workers, and a synthesis step.

    plan (orchestrator, no tools)
      -> substitution worker   2 tools: search_recipes, substitute_ingredient
      -> allergen worker       3 tools: search_recipes, lookup_allergens, lookup_nutrition
                               + the two allergen resources as context; receives the
                               substitution report so it can check the replacement
      -> synthesis (orchestrator, no tools, sees only the worker reports)

Tools come from the same MCP servers and the same mcp_config.json as the Week 9 single
agent, so the two arms differ only in how the work is split. Every hand-off is logged
with the model tokens spent by the side that received it.

A worker is reached through dispatch(), which returns an HTTP-style envelope. Fault
injection makes dispatch() return status 500 for a named worker - simulated at that
boundary, because the workers run in-process.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any, Callable

from mcp_agent import (
    DEFAULT_CONFIG,
    MAX_RATE_LIMIT_ATTEMPTS,
    ToolHub,
    _function_calls,
    _gemini_step,
    connect,
    load_config,
    modelled_cost,
)
from recipe_rag import GEMINI_MODEL, GEMINI_THINKING_LEVEL, _retry_delay, is_rate_limit_error

MAX_WORKER_LAPS = 5
MAX_WORKER_ATTEMPTS = 2  # one retry after a failed dispatch
JSON_START, JSON_END = "{", "}"

PLAN_INSTRUCTION = """You are the orchestrator of a recipe assistant for six South Indian ferment
recipes (idli batter, kallappam, sanna, moru, neeragaram, kuzhi paniyaram). You never answer the
user yourself. Split the question into tasks for two workers and reply with ONLY this JSON:

{"substitution": "<task for the substitution worker>" or null,
 "allergen": "<task for the allergen worker>" or null}

substitution worker: finds a recipe and its ingredient weights, and looks up recorded ingredient
  substitutions. Give it a task when the question asks about a recipe's ingredients or quantities,
  or what to use instead of something.
allergen worker: checks allergen flags and per-100g nutrition for recipes and ingredients. Give it
  a task when the question mentions an allergy, a diet, safety for someone, or nutrition, and
  whenever a substitution is being made for a dietary reason, so the replacement gets checked.

Give at least one worker a task. Write each task as one self-contained sentence."""

SUBSTITUTION_INSTRUCTION = """You are the substitution worker. Complete the task with your tools.
Report only what the tools returned: the recipe_id, the ingredient names and grams you relied on,
and every substitution with the allergens its replacement contains (substitute_contains). If a
tool says no substitute is recorded, report exactly that. Add nothing from your own knowledge.
Reply with a short factual report, not a chat answer."""

ALLERGEN_INSTRUCTION = """You are the allergen and nutrition worker. Complete the task with your
tools and the attached reference context. Report every allergen fact and caveat you found, and
say which source it came from (a tool result or the attached context). Never call something safe
unless a tool result or the attached context supports it; if you cannot establish a fact, say so.
Add nothing from your own knowledge. Reply with a short factual report, not a chat answer."""

SYNTHESIS_INSTRUCTION = """You write the final answer to the user's cooking question, using only
the worker reports you are given. Do not add facts that are not in a report. Keep every allergen
caveat from the allergen worker's report; do not shorten or drop one to make the answer tidier.
If a report is marked UNAVAILABLE, say plainly which check could not be done, and do not fill the
gap yourself. Answer briefly."""

WORKERS: dict[str, dict[str, Any]] = {
    "substitution": {
        "label": "substitution worker",
        "tools": ["search_recipes", "substitute_ingredient"],
        "attach": [],
        "instruction": SUBSTITUTION_INSTRUCTION,
    },
    "allergen": {
        "label": "allergen worker",
        "tools": ["search_recipes", "lookup_allergens", "lookup_nutrition"],
        "attach": ["recipe://allergen-notes", "ingredient-db://allergen-matrix"],
        "instruction": ALLERGEN_INSTRUCTION,
    },
}


def _gemini_text(system_instruction: str, prompt: str) -> Any:
    """One model call with no tools: the orchestrator's plan and synthesis steps."""
    from google import genai

    client = genai.Client()
    for attempt in range(1, MAX_RATE_LIMIT_ATTEMPTS + 1):
        try:
            return client.interactions.create(
                model=GEMINI_MODEL,
                system_instruction=system_instruction,
                input=prompt,
                generation_config={"thinking_level": GEMINI_THINKING_LEVEL},
            )
        except Exception as error:
            if not is_rate_limit_error(error) or attempt == MAX_RATE_LIMIT_ATTEMPTS:
                raise
            time.sleep(_retry_delay(str(error)))
    raise RuntimeError("exhausted Gemini retry attempts")


def _usage(interaction: Any) -> tuple[int, int]:
    """Input and output tokens reported for one call."""
    usage = getattr(interaction, "usage", None)
    if usage is None:
        return 0, 0
    return usage.total_input_tokens or 0, usage.total_output_tokens or 0


def parse_plan(text: str) -> dict[str, str | None]:
    """Read the plan JSON; anything unreadable sends the whole question to both workers."""
    start, end = (text or "").find(JSON_START), (text or "").rfind(JSON_END)
    try:
        plan = json.loads(text[start : end + 1]) if start >= 0 and end > start else None
    except json.JSONDecodeError:
        plan = None
    if not isinstance(plan, dict):
        return {"substitution": "PLAN_UNREADABLE", "allergen": "PLAN_UNREADABLE"}
    return {name: (plan.get(name) or None) for name in WORKERS}


class Ledger:
    """Every hand-off in one run, with the model tokens its receiving side spent."""

    def __init__(self) -> None:
        self.handoffs: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []

    def record(self, handoff: str, payload: str, calls: int, tokens_in: int, tokens_out: int,
               status: str = "ok") -> None:
        """Append one hand-off line."""
        self.handoffs.append({
            "handoff": handoff, "status": status, "payload_chars": len(payload),
            "model_calls": calls, "input_tokens": tokens_in, "output_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        })


async def run_worker(hub: ToolHub, name: str, task: str, generate: Callable[..., Any],
                     ledger: Ledger) -> tuple[str, int, int, int]:
    """One worker's own tool loop, restricted to its tools. Returns report and usage."""
    spec = WORKERS[name]
    missing = [tool for tool in spec["tools"] if tool not in hub.tool_owner]
    if missing:
        raise ValueError(f"{name} worker needs undiscovered tools: {missing}")
    specs = [s for s in hub.function_specs() if s["name"] in spec["tools"]]
    context = "\n\n".join(f"[{uri}]\n{hub.attached[uri]}" for uri in spec["attach"])
    instruction = spec["instruction"] + (f"\n\nReference context:\n\n{context}" if context else "")
    payload: Any = task
    previous: str | None = None
    calls = tokens_in = tokens_out = 0
    while calls < MAX_WORKER_LAPS:
        calls += 1
        interaction = await asyncio.to_thread(generate, instruction, payload, previous, specs)
        used_in, used_out = _usage(interaction)
        tokens_in, tokens_out = tokens_in + used_in, tokens_out + used_out
        steps = _function_calls(interaction)
        if not steps:
            return interaction.output_text or "", calls, tokens_in, tokens_out
        results = []
        for step in steps:
            arguments = dict(step.arguments or {})
            server, is_error, text = await hub.call(step.name, arguments)
            ledger.evidence.append({"worker": name, "server": server, "tool": step.name,
                                    "arguments": arguments, "is_error": is_error, "result": text})
            results.append({"type": "function_result", "call_id": step.id, "name": step.name,
                            "result": {"type": "text", "text": text}, "is_error": is_error})
        payload, previous = results, interaction.id
    return "WORKER STOPPED: lap limit reached before a report", calls, tokens_in, tokens_out


async def dispatch(hub: ToolHub, name: str, task: str, generate: Callable[..., Any],
                   ledger: Ledger, faults: dict[str, int]) -> dict[str, Any]:
    """Send a task to a worker, HTTP-style, retrying once. Logs every attempt."""
    label = WORKERS[name]["label"]
    for attempt in range(1, MAX_WORKER_ATTEMPTS + 1):
        if faults.get(name):
            status = faults[name]
            ledger.record(f"orchestrator -> {label}", task, 0, 0, 0,
                          status=f"HTTP {status} (attempt {attempt})")
            continue
        report, calls, tokens_in, tokens_out = await run_worker(hub, name, task, generate, ledger)
        ledger.record(f"orchestrator -> {label}", task, calls, tokens_in, tokens_out)
        ledger.record(f"{label} -> orchestrator", report, 0, 0, 0)
        return {"status": 200, "report": report, "attempts": attempt}
    return {"status": faults[name], "error": "Internal Server Error",
            "attempts": MAX_WORKER_ATTEMPTS}


async def run_squad(request: str, config: dict[str, dict[str, Any]],
                    generate_text: Callable[..., Any] = _gemini_text,
                    generate_tools: Callable[..., Any] = _gemini_step,
                    faults: dict[str, int] | None = None) -> dict[str, Any]:
    """Plan, delegate, synthesise. Returns the answer, the evidence and the hand-off log."""
    faults = faults or {}
    started = time.monotonic()
    ledger = Ledger()
    async with connect(config) as hub:
        planned = await asyncio.to_thread(generate_text, PLAN_INSTRUCTION, request)
        ledger.record("user -> orchestrator (plan)", request, 1, *_usage(planned))
        plan = parse_plan(planned.output_text or "")

        envelopes: dict[str, dict[str, Any]] = {}
        if plan["substitution"]:
            envelopes["substitution"] = await dispatch(
                hub, "substitution", plan["substitution"], generate_tools, ledger, faults)
        if plan["allergen"]:
            task = plan["allergen"]
            substitution = envelopes.get("substitution", {})
            if substitution.get("status") == 200:
                # The re-send: the allergen worker gets the substitution report to check.
                task += "\n\nSubstitution worker's report, to check:\n" + substitution["report"]
            envelopes["allergen"] = await dispatch(
                hub, "allergen", task, generate_tools, ledger, faults)

        sections = [f"USER QUESTION: {request}"]
        for name, envelope in envelopes.items():
            label = WORKERS[name]["label"].upper()
            if envelope["status"] == 200:
                sections.append(f"{label} REPORT:\n{envelope['report']}")
            else:
                sections.append(f"{label} REPORT: UNAVAILABLE (HTTP {envelope['status']} "
                                f"after {envelope['attempts']} attempts)")
        synthesis_input = "\n\n".join(sections)
        synthesised = await asyncio.to_thread(generate_text, SYNTHESIS_INSTRUCTION, synthesis_input)
        ledger.record("orchestrator -> synthesis", synthesis_input, 1, *_usage(synthesised))

    tokens_in = sum(h["input_tokens"] for h in ledger.handoffs)
    tokens_out = sum(h["output_tokens"] for h in ledger.handoffs)
    return {
        "arm": "squad",
        "request": request,
        "plan": plan,
        "worker_status": {name: env["status"] for name, env in envelopes.items()},
        "answer": synthesised.output_text or "",
        "evidence": ledger.evidence,
        "handoffs": ledger.handoffs,
        "model_calls": sum(h["model_calls"] for h in ledger.handoffs),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "cost_usd": modelled_cost(tokens_in, tokens_out),
        "latency_seconds": round(time.monotonic() - started, 3),
    }


def main() -> None:
    """Run the squad on one request from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("--fail", choices=sorted(WORKERS), help="make this worker return HTTP 500")
    args = parser.parse_args()
    faults = {args.fail: 500} if args.fail else {}
    result = asyncio.run(run_squad(args.request, load_config(DEFAULT_CONFIG), faults=faults))
    print(json.dumps(result["plan"]))
    for handoff in result["handoffs"]:
        print(f"  {handoff['handoff']:<40} {handoff['status']:<22} "
              f"tokens={handoff['total_tokens']}")
    print(f"\nanswer: {result['answer']}")


if __name__ == "__main__":
    main()
