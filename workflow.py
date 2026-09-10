"""The same task as a fixed workflow: parse, search, scale, substitute once, compose.

There is no agent loop here and none hiding inside. The model is called exactly once,
to turn the request into structured arguments; after that the three steps run in a
fixed order and the output is composed in code. The path does not vary by input, which
is precisely the property being raced against the agent.

Same tools, same model, same output contract as agent.py.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable

from agent import JSON_BLOCK_PATTERN, modelled_cost
from recipe_rag import (
    GEMINI_MAX_ATTEMPTS,
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    _retry_delay,
    is_rate_limit_error,
)
from tools import AVOIDABLE, call_tool

EXTRACT_SYSTEM = f"""Turn one recipe request into JSON arguments. Reply with ONLY the JSON,
no prose and no code fence:

{{"dish": str, "target_servings": int or null, "avoid": [str]}}

dish is the dish name as said. target_servings is the requested yield, or null if none was
requested. avoid lists the dietary constraints, each one of exactly: {AVOIDABLE}.
Use [] when the request names no dietary constraint."""


def _gemini_extract(system_instruction: str, request: str) -> Any:
    """One model call, no tools attached: this step only parses the request."""
    from google import genai

    client = genai.Client()
    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
        try:
            return client.interactions.create(
                model=GEMINI_MODEL,
                system_instruction=system_instruction,
                input=request,
                generation_config={"thinking_level": GEMINI_THINKING_LEVEL},
            )
        except Exception as error:
            if not is_rate_limit_error(error) or attempt == GEMINI_MAX_ATTEMPTS:
                raise
            delay = _retry_delay(str(error))
            print(f"    rate limited, retrying in {delay:.0f}s (attempt {attempt})")
            time.sleep(delay)
    raise RuntimeError("exhausted Gemini retry attempts")


def parse_arguments(text: str) -> dict[str, Any]:
    """Read the extraction call's JSON, falling back to empty arguments."""
    match = JSON_BLOCK_PATTERN.search(text or "")
    if match is None:
        return {"dish": "", "target_servings": None, "avoid": []}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"dish": "", "target_servings": None, "avoid": []}
    avoid = [a for a in parsed.get("avoid") or [] if a in AVOIDABLE]
    return {
        "dish": parsed.get("dish") or "",
        "target_servings": parsed.get("target_servings"),
        "avoid": avoid,
    }


def _first_substitution(ingredients: list[dict[str, Any]], avoid: str) -> dict[str, Any] | None:
    """Bounded scan for the card ingredient this constraint hits.

    A fixed scan over a known ingredient list, not a decision loop: it makes no model
    calls and cannot revisit its own output.
    """
    for row in ingredients:
        result = call_tool("substitute_ingredient", {"ingredient": row["ingredient"], "avoid": avoid})
        if result.get("substituted"):
            return result
    return None


def run_workflow(
    request: str,
    extract: Callable[[str, str], Any] = _gemini_extract,
) -> dict[str, Any]:
    """Three fixed steps. One model call, at the front, for parsing only."""
    started = time.monotonic()
    log: list[str] = []
    input_tokens = output_tokens = 0

    interaction = extract(EXTRACT_SYSTEM, request)
    usage = getattr(interaction, "usage", None)
    if usage is not None:
        input_tokens += usage.total_input_tokens or 0
        output_tokens += usage.total_output_tokens or 0
    arguments = parse_arguments(interaction.output_text or "")
    log.append(f"step 0 (model): extracted {json.dumps(arguments)}")

    # Step 1 - search.
    found = call_tool("search_recipes", {"dish": arguments["dish"] or request})
    log.append(f"step 1: search_recipes -> {found.get('recipe_id')}")
    if not found.get("found"):
        return _result(request, None, log, input_tokens, output_tokens, started, "no_recipe")

    # Step 2 - scale.
    target = arguments["target_servings"] or found["base_yield"]
    scaled = call_tool(
        "scale_recipe", {"recipe_id": found["recipe_id"], "target_servings": int(target)}
    )
    log.append(f"step 2: scale_recipe -> factor {scaled.get('factor')}")
    if not scaled.get("scaled"):
        return _result(request, None, log, input_tokens, output_tokens, started, "scale_failed")

    # Step 3 - substitute, exactly once. No re-checking of the replacement: that is the
    # capability the fixed workflow gives up, and the cascade cases are where it shows.
    substitutions: list[list[str]] = []
    no_safe_substitute = False
    if arguments["avoid"]:
        constraint = arguments["avoid"][0]
        swap = _first_substitution(scaled["ingredients"], constraint)
        if swap is None:
            no_safe_substitute = True
            log.append(f"step 3: no substitution found for {constraint}")
        else:
            substitutions.append([swap["ingredient"], swap["substitute"]])
            log.append(
                f"step 3: {swap['ingredient']} -> {swap['substitute']} "
                f"(contains {swap['substitute_contains']}), not re-checked"
            )
    else:
        log.append("step 3: no dietary constraint, skipped")

    contract = {
        "recipe_id": found["recipe_id"],
        "target_servings": int(target),
        "factor": scaled["factor"],
        "substitutions": substitutions,
        "no_safe_substitute": no_safe_substitute,
    }
    return _result(request, contract, log, input_tokens, output_tokens, started, "completed")


def _result(
    request: str,
    contract: dict[str, Any] | None,
    log: list[str],
    input_tokens: int,
    output_tokens: int,
    started: float,
    stop_reason: str,
) -> dict[str, Any]:
    """Package the workflow run in the same shape the agent returns."""
    return {
        "system": "workflow",
        "request": request,
        "output": contract,
        "raw_output": json.dumps(contract) if contract else "",
        "laps": 1,
        "model_calls": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": modelled_cost(input_tokens, output_tokens),
        "latency_seconds": round(time.monotonic() - started, 3),
        "stop_reason": stop_reason,
        "log": log,
    }


def main() -> None:
    """Run the workflow on one request from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="the recipe adaptation request")
    args = parser.parse_args()
    result = run_workflow(args.request)
    for line in result["log"]:
        print("  " + line)
    print(f"\nstop_reason : {result['stop_reason']}")
    print(f"model calls : {result['model_calls']}")
    print(f"tokens      : {result['total_tokens']}")
    print(f"cost        : ${result['cost_usd']:.5f}")
    print(f"latency     : {result['latency_seconds']}s")
    print(f"output      : {json.dumps(result['output'], indent=2) if result['output'] else None}")


if __name__ == "__main__":
    main()
