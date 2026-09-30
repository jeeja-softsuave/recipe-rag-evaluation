"""Check the squad's control flow against the real MCP servers, with every model call
stubbed. Zero API calls: tool scoping, the re-send, hand-off accounting and fault
handling are plumbing, so they are tested as plumbing.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from mcp_agent import DEFAULT_CONFIG, load_config
from orchestrator import MAX_WORKER_ATTEMPTS, MAX_WORKER_LAPS, WORKERS, parse_plan, run_squad
from race10 import nearest_rank

CHECKS: list[tuple[str, bool]] = []
USAGE = SimpleNamespace(total_input_tokens=100, total_output_tokens=10)


def check(label: str, passed: bool) -> None:
    """Record one named check."""
    CHECKS.append((label, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {label}")


def text_stub(plan: str, seen: list[tuple[str, str]]):
    """Plan and synthesis stub: returns the plan first, then a fixed answer."""

    def generate(instruction: str, prompt: str) -> Any:
        seen.append((instruction, prompt))
        text = plan if len(seen) == 1 else "final answer"
        return SimpleNamespace(output_text=text, usage=USAGE)

    return generate


def tool_stub(seen: list[dict[str, Any]], endless: bool = False):
    """Worker stub: one real tool call on the first lap, then a report."""
    first_call = {"substitution": ("substitute_ingredient",
                                   {"ingredient": "Thick sour curd", "avoid": "dairy"}),
                  "allergen": ("lookup_allergens", {"ingredient": "coconut milk yoghurt"})}

    def generate(instruction: str, payload: Any, previous: str | None, specs: Any) -> Any:
        worker = "substitution" if "substitution worker" in instruction.split(".")[0] else "allergen"
        seen.append({"worker": worker, "tools": [s["name"] for s in specs],
                     "payload": payload, "instruction": instruction})
        if previous is None or endless:
            name, arguments = first_call[worker]
            step = SimpleNamespace(type="function_call", id="c1", name=name, arguments=arguments)
            return SimpleNamespace(id="i1", steps=[step], output_text=None, usage=USAGE)
        return SimpleNamespace(id="i2", steps=[], output_text=f"{worker} report", usage=USAGE)

    return generate


async def main() -> None:
    """Every check, against the servers in mcp_config.json."""
    config = load_config(DEFAULT_CONFIG)
    both = '{"substitution": "find a dairy swap for moru", "allergen": "check the swap"}'

    texts: list[tuple[str, str]] = []
    tools: list[dict[str, Any]] = []
    result = await run_squad("dairy free moru", config, text_stub(both, texts), tool_stub(tools))
    offered = {entry["worker"]: set(entry["tools"]) for entry in tools}
    check("substitution worker is offered only its own tools",
          offered["substitution"] == set(WORKERS["substitution"]["tools"]))
    check("allergen worker is offered only its own tools",
          offered["allergen"] == set(WORKERS["allergen"]["tools"]))
    first_allergen = next(entry for entry in tools if entry["worker"] == "allergen")
    check("allergen worker receives the substitution report (the re-send)",
          "substitution report" in first_allergen["payload"])
    check("allergen worker gets its attached resources; substitution worker gets none",
          all(uri in first_allergen["instruction"] for uri in WORKERS["allergen"]["attach"])
          and not any("Reference context" in e["instruction"] for e in tools
                      if e["worker"] == "substitution"))
    check("synthesis sees both worker reports", "substitution report" in texts[-1][1]
          and "allergen report" in texts[-1][1])
    check("hand-off tokens add up to the run total",
          sum(h["total_tokens"] for h in result["handoffs"]) == result["total_tokens"])
    check("model calls: plan 1 + two workers x 2 laps + synthesis 1 = 6",
          result["model_calls"] == 6)
    check("raw tool results are kept as evidence, per worker",
          [e["worker"] for e in result["evidence"]] == ["substitution", "allergen"]
          and all(not e["is_error"] for e in result["evidence"]))

    texts, tools = [], []
    result = await run_squad("dairy free moru", config, text_stub(both, texts), tool_stub(tools),
                             faults={"allergen": 500})
    attempts = [h for h in result["handoffs"] if h["handoff"] == "orchestrator -> allergen worker"]
    check("a 500 from the allergen worker is retried, then given up",
          len(attempts) == MAX_WORKER_ATTEMPTS and all("HTTP 500" in h["status"] for h in attempts))
    check("the failed worker spends no model tokens",
          all(h["total_tokens"] == 0 for h in attempts)
          and not any(entry["worker"] == "allergen" for entry in tools))
    check("synthesis is told the allergen report is UNAVAILABLE",
          "ALLERGEN WORKER REPORT: UNAVAILABLE (HTTP 500" in texts[-1][1])
    check("worker status records the 500", result["worker_status"]["allergen"] == 500)

    check("unreadable plan sends the question to both workers",
          parse_plan("I think the user wants...") == {name: "PLAN_UNREADABLE" for name in WORKERS})
    check("a null task skips that worker",
          parse_plan('{"substitution": null, "allergen": "x"}') == {"substitution": None, "allergen": "x"})

    tools = []
    result = await run_squad("x", config, text_stub('{"substitution": "loop", "allergen": null}', []),
                             tool_stub(tools, endless=True))
    check("a worker that never stops is cut off at the lap limit",
          len(tools) == MAX_WORKER_LAPS and "allergen" not in result["worker_status"])

    check("p99 of 10 runs is the slowest run", nearest_rank(list(range(1, 11)), 99) == 10)
    check("p50 of 10 runs is the 5th fastest (nearest rank)", nearest_rank(list(range(1, 11)), 50) == 5)

    failed = [label for label, passed in CHECKS if not passed]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed, 0 API calls")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
