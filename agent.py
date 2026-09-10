"""The agent loop: the model chooses which tool to call, lap after lap, until done.

All four budgets are checked on every lap, not merely declared as constants. An
unenforced budget is a comment with ambition.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any, Callable

from recipe_rag import (
    GEMINI_MAX_ATTEMPTS,
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    _retry_delay,
    is_rate_limit_error,
)
from tools import TOOL_SPECS, call_tool

# --- budgets. Every one of these is checked in the loop below. ---
MAX_ITERATIONS = 8
MAX_TOKENS = 20000
MAX_COST_USD = 0.02
MAX_WALL_CLOCK_SECONDS = 90.0

# Cost model. STATED ASSUMPTION, not a billed rate: the free tier bills nothing, so
# cost is modelled from token counts at these list prices. Replace with your own rate.
PRICE_INPUT_PER_1M_USD = 0.30
PRICE_OUTPUT_PER_1M_USD = 2.50

JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_INSTRUCTION = """You adapt South Indian ferment recipes using the three tools provided.

Work in this order, using tools rather than your own knowledge:
1. Find the recipe with search_recipes.
2. Scale it with scale_recipe to the requested yield. If no yield is requested, use the base yield.
3. If the user named a dietary constraint, call substitute_ingredient for the offending ingredient.
   Read substitute_contains in the result. If the replacement itself contains something the user
   is avoiding, call substitute_ingredient AGAIN on that replacement. Repeat until the replacement
   violates none of the user's constraints, or the tool reports no substitution exists.

When every constraint is satisfied, stop calling tools and say briefly what you changed.
Your final wording is not graded: the answer is assembled from the tool results you obtained,
exactly as it is for the fixed workflow. What is graded is which tools you called and with
what arguments."""


def modelled_cost(input_tokens: int, output_tokens: int) -> float:
    """Cost in USD from token counts, using the stated list-price assumption."""
    return (
        input_tokens * PRICE_INPUT_PER_1M_USD + output_tokens * PRICE_OUTPUT_PER_1M_USD
    ) / 1_000_000


def _gemini_step(system_instruction: str, payload: Any, previous_id: str | None) -> Any:
    """One model call with tools attached. Returns the raw Interaction.

    The first lap sends the request as a string. Later laps send only the new
    function results and point at the previous interaction, which the API continues
    server-side; a user_input step is not accepted on the input side.
    """
    from google import genai

    client = genai.Client()
    request: dict[str, Any] = {
        "model": GEMINI_MODEL,
        "input": payload,
        "tools": TOOL_SPECS,
        "generation_config": {"thinking_level": GEMINI_THINKING_LEVEL},
    }
    if previous_id is None:
        request["system_instruction"] = system_instruction
    else:
        request["previous_interaction_id"] = previous_id

    # A lap that trips the per-minute limit is not a spent day: back off and retry.
    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
        try:
            return client.interactions.create(**request)
        except Exception as error:
            if not is_rate_limit_error(error) or attempt == GEMINI_MAX_ATTEMPTS:
                raise
            delay = _retry_delay(str(error))
            print(f"    rate limited, retrying in {delay:.0f}s (attempt {attempt})")
            time.sleep(delay)
    raise RuntimeError("exhausted Gemini retry attempts")


def _norm(text: Any) -> str:
    """Normalise an ingredient name for comparison."""
    return " ".join(str(text).strip().lower().split())


def parse_contract(text: str) -> dict[str, Any] | None:
    """Pull the output-contract JSON out of the model's final message."""
    if not text:
        return None
    match = JSON_BLOCK_PATTERN.search(text)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _function_calls(interaction: Any) -> list[Any]:
    """Every function_call step the model emitted on this lap."""
    return [
        step
        for step in (interaction.steps or [])
        if getattr(step, "type", None) == "function_call"
    ]


def run_agent(
    request: str,
    generate: Callable[[str, Any, str | None], Any] = _gemini_step,
    max_iterations: int = MAX_ITERATIONS,
    max_tokens: int = MAX_TOKENS,
    max_cost_usd: float = MAX_COST_USD,
    max_wall_clock_seconds: float = MAX_WALL_CLOCK_SECONDS,
) -> dict[str, Any]:
    """Run the loop until the model answers or a budget stops it."""
    started = time.monotonic()
    payload: Any = request
    previous_id: str | None = None
    log: list[str] = []
    laps = 0
    input_tokens = output_tokens = 0
    stop_reason = "completed"
    raw_output = ""
    # Observed tool results, from which the output contract is composed in code.
    found: dict[str, Any] | None = None
    scaled: dict[str, Any] | None = None
    swaps: list[list[str]] = []
    dead_end = False

    while True:
        elapsed = time.monotonic() - started
        cost = modelled_cost(input_tokens, output_tokens)
        # --- all four budgets, checked before spending another lap ---
        if laps >= max_iterations:
            stop_reason = "budget:max_iterations"
            log.append(f"STOP {stop_reason} after {laps} laps (limit {max_iterations})")
            break
        if input_tokens + output_tokens >= max_tokens:
            stop_reason = "budget:max_tokens"
            log.append(
                f"STOP {stop_reason} at {input_tokens + output_tokens} tokens "
                f"(limit {max_tokens})"
            )
            break
        if cost >= max_cost_usd:
            stop_reason = "budget:max_cost"
            log.append(f"STOP {stop_reason} at ${cost:.5f} (limit ${max_cost_usd})")
            break
        if elapsed >= max_wall_clock_seconds:
            stop_reason = "budget:wall_clock"
            log.append(
                f"STOP {stop_reason} at {elapsed:.1f}s (limit {max_wall_clock_seconds}s)"
            )
            break

        laps += 1
        interaction = generate(SYSTEM_INSTRUCTION, payload, previous_id)
        usage = getattr(interaction, "usage", None)
        if usage is not None:
            # Summed per lap: the loop resends the whole step list, so counting only
            # the last call would understate the agent's cost by multiples.
            input_tokens += usage.total_input_tokens or 0
            output_tokens += usage.total_output_tokens or 0

        calls = _function_calls(interaction)
        if not calls:
            raw_output = interaction.output_text or ""
            log.append(f"lap {laps}: stopped calling tools")
            break

        results: list[dict[str, Any]] = []
        for call in calls:
            result = call_tool(call.name, dict(call.arguments or {}))
            log.append(
                f"lap {laps}: {call.name}({json.dumps(call.arguments)}) "
                f"-> {json.dumps(result)[:120]}"
            )
            if call.name == "search_recipes" and result.get("found"):
                found = result
            elif call.name == "scale_recipe" and result.get("scaled"):
                scaled = result
            elif call.name == "substitute_ingredient":
                if result.get("substituted"):
                    swaps.append([result["ingredient"], result["substitute"]])
                    dead_end = False
                elif swaps and _norm(result.get("ingredient")) == _norm(swaps[-1][1]):
                    # The chain ran out: the last replacement itself has no substitute.
                    dead_end = True
            results.append(
                {
                    "type": "function_result",
                    "call_id": call.id,
                    "name": call.name,
                    "result": {"type": "text", "text": json.dumps(result)},
                }
            )
        payload = results
        previous_id = interaction.id

    contract = None
    if found and scaled:
        contract = {
            "recipe_id": found["recipe_id"],
            "target_servings": scaled["target_servings"],
            "factor": scaled["factor"],
            "substitutions": swaps,
            "no_safe_substitute": dead_end,
        }

    return {
        "system": "agent",
        "request": request,
        "output": contract,
        "raw_output": raw_output,
        "laps": laps,
        "model_calls": laps,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": modelled_cost(input_tokens, output_tokens),
        "latency_seconds": round(time.monotonic() - started, 3),
        "stop_reason": stop_reason,
        "log": log,
    }


def main() -> None:
    """Run the agent on one request from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="the recipe adaptation request")
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-cost", type=float, default=MAX_COST_USD)
    parser.add_argument("--max-seconds", type=float, default=MAX_WALL_CLOCK_SECONDS)
    args = parser.parse_args()

    result = run_agent(
        args.request,
        max_iterations=args.max_iterations,
        max_tokens=args.max_tokens,
        max_cost_usd=args.max_cost,
        max_wall_clock_seconds=args.max_seconds,
    )
    print(f"budgets: iterations={args.max_iterations} tokens={args.max_tokens} "
          f"cost=${args.max_cost} wall_clock={args.max_seconds}s")
    for line in result["log"]:
        print("  " + line)
    print(f"\nstop_reason : {result['stop_reason']}")
    print(f"laps        : {result['laps']}")
    print(f"tokens      : {result['total_tokens']} "
          f"(in {result['input_tokens']} / out {result['output_tokens']})")
    print(f"cost        : ${result['cost_usd']:.5f}")
    print(f"latency     : {result['latency_seconds']}s")
    print(f"output      : {json.dumps(result['output'], indent=2) if result['output'] else None}")


if __name__ == "__main__":
    main()
