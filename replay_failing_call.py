"""Replay one failing tool call two ways, so the error message is the only variable.

Lap 1 is a real model call with the BASELINE tool descriptions, copied verbatim from
tools_before.json (the raw tools/list recorded at commit 5963d57). If the model emits a
substitute_ingredient call that fails on its name, that one interaction is continued
twice from the same interaction id:

  before - answered as the baseline server answered it: tools.py's result, unchanged,
           with the baseline descriptions still attached;
  after  - answered by the current recipe_server.py over MCP, with the rewritten
           descriptions attached from lap 2 on.

mcp_agent.py is used, not modified: same instruction, same model step, same parsing.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import tools
from mcp_agent import (
    ToolHub,
    _function_calls,
    _gemini_step,
    _strip_schema,
    build_instruction,
    connect,
    load_config,
)

PROJECT_DIR = Path(__file__).parent
BEFORE_LISTING = PROJECT_DIR / "tools_before.json"
CONFIG = PROJECT_DIR / "mcp_config.server_one.json"
OUT = PROJECT_DIR / "error_replay.json"
REQUEST = "What can I use instead of curd if I'm avoiding dairy?"
MAX_BRANCH_LAPS = 4


def baseline_specs() -> list[dict[str, Any]]:
    """The model-facing tool specs exactly as the baseline server listed them."""
    listing = json.loads(BEFORE_LISTING.read_text(encoding="utf-8"))["tools_list"]
    return [
        {"type": "function", "name": tool["name"], "description": tool.get("description") or "",
         "parameters": _strip_schema(tool["inputSchema"])}
        for server_tools in listing.values()
        for tool in server_tools
    ]


def baseline_call(name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Answer a call as the baseline server did: a pass-through to tools.py."""
    return False, json.dumps(tools.call_tool(name, arguments), indent=2)


def _step(call: Any, is_error: bool, text: str) -> dict[str, Any]:
    """One function_result step, in the shape mcp_agent.py sends."""
    return {"type": "function_result", "call_id": call.id, "name": call.name,
            "result": {"type": "text", "text": text}, "is_error": is_error}


async def branch(label: str, instruction: str, first: Any, answer, specs) -> dict[str, Any]:
    """Continue the shared lap-1 interaction with one way of answering tool calls."""
    transcript: list[dict[str, Any]] = []
    interaction, laps = first, 1
    while True:
        calls = _function_calls(interaction)
        if not calls:
            return {"branch": label, "laps": laps, "transcript": transcript,
                    "answer": interaction.output_text or ""}
        if laps > MAX_BRANCH_LAPS:
            return {"branch": label, "laps": laps, "transcript": transcript,
                    "answer": None, "stop": "lap limit"}
        results = []
        for call in calls:
            arguments = dict(call.arguments or {})
            is_error, text = await answer(call.name, arguments)
            transcript.append({"lap": laps, "tool": call.name, "arguments": arguments,
                               "is_error": is_error, "result": json.loads(text)
                               if text.startswith("{") else text})
            results.append(_step(call, is_error, text))
        laps += 1
        interaction = await asyncio.to_thread(
            _gemini_step, instruction, results, interaction.id, specs
        )


async def main() -> None:
    """Lap 1 once, then both branches from the same interaction."""
    async with connect(load_config(CONFIG)) as hub:
        instruction = build_instruction(hub)
        old_specs = baseline_specs()
        first = await asyncio.to_thread(_gemini_step, instruction, REQUEST, None, old_specs)
        calls = _function_calls(first)
        record: dict[str, Any] = {
            "request": REQUEST,
            "lap1_interaction_id": first.id,
            "lap1_calls": [{"tool": c.name, "arguments": dict(c.arguments or {})} for c in calls],
        }
        probe = [baseline_call(c.name, dict(c.arguments or {})) for c in calls]
        failing = any(c.name == "substitute_ingredient" and '"substituted": false' in text
                      for c, (_, text) in zip(calls, probe))
        if not failing:
            record["outcome"] = "lap 1 made no failing substitute_ingredient call; nothing to replay"
        else:
            async def old(name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
                return baseline_call(name, arguments)

            async def new(name: str, arguments: dict[str, Any], _hub: ToolHub = hub):
                _server, is_error, text = await _hub.call(name, arguments)
                return is_error, text

            record["before"] = await branch("before", instruction, first, old, old_specs)
            record["after"] = await branch("after", instruction, first, new, hub.function_specs())
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
