"""Check MCP discovery, routing and the agent loop against the real servers, with the model
stubbed. Zero API calls: discovery and routing are plumbing, so they are tested as plumbing.

Nothing here names a server's tools as expected constants. Every expectation is derived
from what tools/list returned, so the checks hold whatever the config contains.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from mcp_agent import DEFAULT_CONFIG, connect, list_tools, load_config, run_agent

CHECKS: list[tuple[str, bool]] = []


def check(label: str, passed: bool) -> None:
    """Record one named check."""
    CHECKS.append((label, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {label}")


def _call(name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    """A stand-in for a FunctionCallStep."""
    return SimpleNamespace(type="function_call", id=f"c-{name}", name=name, arguments=arguments)


def scripted_model(script: list[list[SimpleNamespace]], seen: list[Any]):
    """A model stub that emits the scripted calls lap by lap, then a final answer."""

    def generate(_instruction: str, payload: Any, _previous: str | None, specs: Any) -> Any:
        seen.append({"payload": payload, "specs": specs, "instruction": _instruction})
        lap = len(seen) - 1
        usage = SimpleNamespace(total_input_tokens=100, total_output_tokens=20)
        if lap < len(script):
            return SimpleNamespace(id=f"i{lap}", steps=script[lap], output_text=None, usage=usage)
        return SimpleNamespace(id=f"i{lap}", steps=[], output_text="done", usage=usage)

    return generate


async def main() -> None:
    """Run every check against the servers in mcp_config.json."""
    config = load_config(DEFAULT_CONFIG)
    listing = await list_tools(config)
    names = [name for tools in listing["tools_by_server"].values() for name in tools]

    check("every configured server connected", listing["servers"] == sorted(config))
    check("tool count equals the names tools/list returned", listing["tool_count"] == len(names))
    check("no tool name is offered twice", len(names) == len(set(names)))

    async with connect(config) as hub:
        specs = hub.function_specs()
        check("one model spec per discovered tool", [s["name"] for s in specs] == names)
        check("schemas reach the model without SDK 'title' keys",
              "title" not in json.dumps([s["parameters"] for s in specs]))
        listed = {uri for entry in config.values() for uri in entry.get("attachResources", [])}
        check("every attachResources URI was read", set(hub.attached) == listed)
        server, is_error, text = await hub.call("no_such_tool", {})
        check("unknown tool comes back as an error, not an exception",
              server is None and is_error and "no_such_tool" in text)

    # First discovered tool called with no arguments: the server's own validation must
    # reach the model as isError=True rather than crash the loop.
    first = names[0]
    seen: list[Any] = []
    result = await run_agent("stub", config, generate=scripted_model([[_call(first, {})]], seen))
    check("a bad-argument call is routed and flagged is_error",
          result["calls"][0]["tool"] == first and result["calls"][0]["is_error"])
    check("the error result is handed back to the model with is_error set",
          seen[1]["payload"][0]["is_error"] is True)
    check("trace names the server that answered",
          result["calls"][0]["server"] == hub.tool_owner[first])
    check("the model is offered exactly the discovered tools",
          [s["name"] for s in seen[0]["specs"]] == names)
    check("attached resources are in the instruction, not fetched by a tool call",
          all(uri in seen[0]["instruction"] for uri in listed))
    check("loop ends on a plain answer", result["stop_reason"] == "completed")

    forever = [[_call(first, {})]] * 20
    result = await run_agent("stub", config, generate=scripted_model(forever, []),
                             max_iterations=3)
    check("max_iterations budget stops the loop", result["stop_reason"] == "budget:max_iterations"
          and result["laps"] == 3)
    result = await run_agent("stub", config, generate=scripted_model(forever, []),
                             max_tokens=250)
    check("max_tokens budget stops the loop", result["stop_reason"] == "budget:max_tokens")

    failed = [label for label, passed in CHECKS if not passed]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed, 0 API calls")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
