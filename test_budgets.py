"""Prove every budget is enforced, and both systems work, without spending a single call.

The model is stubbed. That is the point: budget enforcement is control flow, so it can
and should be tested without the API.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from agent import run_agent
from workflow import run_workflow


def _usage(input_tokens: int, output_tokens: int) -> SimpleNamespace:
    """A stand-in for the SDK Usage object."""
    return SimpleNamespace(total_input_tokens=input_tokens, total_output_tokens=output_tokens)


def _call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> SimpleNamespace:
    """A stand-in for a FunctionCallStep."""
    return SimpleNamespace(type="function_call", id=call_id, name=name, arguments=arguments)


def stub_happy_path(tokens: tuple[int, int] = (100, 40)):
    """Search, then scale, then answer: the three-lap path a simple request needs."""
    laps: list[Any] = []

    def generate(_system: str, _payload: Any, previous_id: str | None, _tools: Any = None) -> SimpleNamespace:
        laps.append(previous_id)
        made = len([x for x in laps if x is not None])
        if made == 0:
            return SimpleNamespace(
                id="i1",
                steps=[_call("search_recipes", {"dish": "moru"})],
                output_text=None,
                usage=_usage(*tokens),
            )
        if made == 1:
            return SimpleNamespace(
                id="i2",
                steps=[_call("scale_recipe", {"recipe_id": "moru-04", "target_servings": 16}, "c2")],
                output_text=None,
                usage=_usage(*tokens),
            )
        final = {
            "recipe_id": "moru-04",
            "target_servings": 16,
            "ingredients": [{"ingredient": "Thick sour curd", "grams": 800.0}],
            "substitutions": [],
            "no_safe_substitute": False,
        }
        return SimpleNamespace(id="i3", steps=[], output_text=json.dumps(final), usage=_usage(*tokens))

    return generate


def stub_never_stops(tokens: tuple[int, int] = (100, 40)):
    """Always asks for another tool call: what a spinning agent looks like."""

    counter = {"n": 0}

    def generate(_system: str, _payload: Any, _previous_id: str | None, _tools: Any = None) -> SimpleNamespace:
        counter["n"] += 1
        return SimpleNamespace(
            id=f"i{counter['n']}",
            steps=[_call("search_recipes", {"dish": "moru"}, f"c{counter['n']}")],
            output_text=None,
            usage=_usage(*tokens),
        )

    return generate


def check(label: str, got: Any, want: Any) -> bool:
    """Print one comparison and say whether it held."""
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    """Run every budget and plumbing check."""
    failures = 0

    print("agent completes a normal request")
    result = run_agent("moru for 16 glasses", generate=stub_happy_path())
    failures += not check("stop_reason", result["stop_reason"], "completed")
    failures += not check("laps", result["laps"], 3)
    failures += not check("tokens summed over laps", result["total_tokens"], 3 * 140)
    failures += not check("output parsed", bool(result["output"]), True)

    print("\nbudget 1 of 4: max_iterations")
    result = run_agent("moru", generate=stub_never_stops(), max_iterations=4)
    failures += not check("stop_reason", result["stop_reason"], "budget:max_iterations")
    failures += not check("laps stopped at limit", result["laps"], 4)

    print("\nbudget 2 of 4: max_tokens")
    result = run_agent(
        "moru", generate=stub_never_stops((5000, 1000)), max_iterations=99, max_tokens=12000
    )
    failures += not check("stop_reason", result["stop_reason"], "budget:max_tokens")
    failures += not check("laps before tokens ran out", result["laps"], 2)

    print("\nbudget 3 of 4: max_cost")
    result = run_agent(
        "moru",
        generate=stub_never_stops((100_000, 100_000)),
        max_iterations=99,
        max_tokens=10_000_000,
        max_cost_usd=0.5,
    )
    failures += not check("stop_reason", result["stop_reason"], "budget:max_cost")

    print("\nbudget 4 of 4: wall_clock")
    result = run_agent(
        "moru", generate=stub_never_stops(), max_iterations=99, max_wall_clock_seconds=0.0
    )
    failures += not check("stop_reason", result["stop_reason"], "budget:wall_clock")
    failures += not check("no laps spent", result["laps"], 0)

    print("\nworkflow runs its three fixed steps")
    def stub_extract(_system: str, _request: str) -> SimpleNamespace:
        return SimpleNamespace(
            output_text=json.dumps({"dish": "moru", "target_servings": 16, "avoid": ["dairy"]}),
            usage=_usage(120, 30),
        )

    result = run_workflow("moru for 16 glasses, dairy free", extract=stub_extract)
    failures += not check("stop_reason", result["stop_reason"], "completed")
    failures += not check("model calls", result["model_calls"], 1)
    failures += not check("recipe", result["output"]["recipe_id"], "moru-04")
    failures += not check(
        "one swap only",
        result["output"]["substitutions"],
        [["Thick sour curd", "coconut milk yoghurt"]],
    )

    print(f"\n{failures} failure(s)")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
