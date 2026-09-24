"""The Week 9 agent: every tool it can call is discovered over MCP, never imported.

Which servers exist is read from mcp_config.json. Which tools exist is read from each
server's tools/list at start-up. Nothing in this module names a tool or counts them, so
adding a server is a config change and this file does not move. The model runs here, in
the host, and only here: the servers never call a model.

Resources are handled differently from tools on purpose. A resource the config lists
under attachResources is read once and put in the system instruction by the app; a tool
is something the model chooses to call. Standing context belongs in the first group.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from mcp import ClientSession, StdioServerParameters, stdio_client

from recipe_rag import (
    GEMINI_MODEL,
    GEMINI_THINKING_LEVEL,
    _retry_delay,
    is_rate_limit_error,
)

PROJECT_DIR = Path(__file__).parent
DEFAULT_CONFIG = PROJECT_DIR / "mcp_config.json"
DEFAULT_TRACE = PROJECT_DIR / "mcp_traces.jsonl"

# --- budgets: the same four values as the Week 7 agent, each checked every lap. ---
MAX_ITERATIONS = 8
MAX_TOKENS = 20000
MAX_COST_USD = 0.02
MAX_WALL_CLOCK_SECONDS = 90.0
# Stated assumption, not a billed rate (free tier): the Week 7 list prices.
PRICE_INPUT_PER_1M_USD = 0.30
PRICE_OUTPUT_PER_1M_USD = 2.50
# A daily-quota 429 also says "retry in 31s"; retrying it only burns attempts.
MAX_RATE_LIMIT_ATTEMPTS = 2
# JSON-Schema keys the SDK emits for humans that the model does not need.
SCHEMA_KEYS_DROPPED = {"title"}

SYSTEM_INSTRUCTION = """You adapt South Indian ferment recipes and answer questions about their
ingredients, using the tools provided. Use tool results rather than your own knowledge for
recipe quantities, substitutions, allergens and nutrition.

If a tool reports an error or no match, read its message: it may tell you how to correct the
call. Retry with corrected arguments when it does. Never state an allergen, substitution or
nutrition value that no tool returned.

When you have what you need, stop calling tools and answer briefly."""


def modelled_cost(input_tokens: int, output_tokens: int) -> float:
    """Cost in USD from token counts, using the stated list-price assumption."""
    return (
        input_tokens * PRICE_INPUT_PER_1M_USD + output_tokens * PRICE_OUTPUT_PER_1M_USD
    ) / 1_000_000


def load_config(path: Path) -> dict[str, dict[str, Any]]:
    """Read the mcpServers block: one entry per server, in the usual host format."""
    return json.loads(path.read_text(encoding="utf-8"))["mcpServers"]


def _strip_schema(node: Any) -> Any:
    """Drop presentation-only keys from a tool's inputSchema, recursively."""
    if isinstance(node, dict):
        return {
            key: _strip_schema(value)
            for key, value in node.items()
            if key not in SCHEMA_KEYS_DROPPED
        }
    if isinstance(node, list):
        return [_strip_schema(item) for item in node]
    return node


class ToolHub:
    """Live sessions to every configured server, and what each one said it offers."""

    def __init__(self) -> None:
        self.sessions: dict[str, ClientSession] = {}
        self.tool_owner: dict[str, str] = {}
        self.tools_list: dict[str, list[dict[str, Any]]] = {}
        self.attached: dict[str, str] = {}

    def function_specs(self) -> list[dict[str, Any]]:
        """Every discovered tool, in the function format the model API takes."""
        return [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool.get("description") or "",
                "parameters": _strip_schema(tool["inputSchema"]),
            }
            for tools in self.tools_list.values()
            for tool in tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str | None, bool, str]:
        """Route one tools/call to the server that listed the tool. Never raises."""
        server = self.tool_owner.get(name)
        if server is None:
            return None, True, f"no connected server offers a tool named {name}"
        try:
            result = await self.sessions[server].call_tool(name, arguments)
        except Exception as error:  # a dead server must reach the model as a dead server
            return server, True, f"server {server} failed: {type(error).__name__}: {error}"
        text = "\n".join(
            block.text for block in result.content if getattr(block, "type", None) == "text"
        )
        return server, bool(result.is_error), text


@asynccontextmanager
async def connect(config: dict[str, dict[str, Any]]) -> AsyncIterator[ToolHub]:
    """Start every configured server, then discover its tools and attach its resources."""
    hub = ToolHub()
    async with AsyncExitStack() as stack:
        for name, entry in config.items():
            params = StdioServerParameters(
                command=entry["command"],
                args=entry.get("args", []),
                env=entry.get("env"),
                cwd=entry.get("cwd", str(PROJECT_DIR)),
            )
            streams = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(*streams))
            await session.initialize()
            listing = await session.list_tools()
            tools = [tool.model_dump(by_alias=True, exclude_none=True) for tool in listing.tools]
            for tool in tools:
                if tool["name"] in hub.tool_owner:
                    raise ValueError(
                        f"tool {tool['name']} offered by both "
                        f"{hub.tool_owner[tool['name']]} and {name}"
                    )
                hub.tool_owner[tool["name"]] = name
            hub.sessions[name] = session
            hub.tools_list[name] = tools
            for uri in entry.get("attachResources", []):
                read = await session.read_resource(uri)
                hub.attached[uri] = "\n".join(
                    part.text for part in read.contents if getattr(part, "text", None)
                )
        yield hub


def build_instruction(hub: ToolHub) -> str:
    """The system instruction, with every app-attached resource appended as context."""
    if not hub.attached:
        return SYSTEM_INSTRUCTION
    context = "\n\n".join(f"[{uri}]\n{text}" for uri, text in hub.attached.items())
    return f"{SYSTEM_INSTRUCTION}\n\nReference context attached by the app:\n\n{context}"


def _gemini_step(
    system_instruction: str, payload: Any, previous_id: str | None, tools: Any
) -> Any:
    """One model call with the discovered tools attached. Returns the raw Interaction."""
    from google import genai

    client = genai.Client()
    request: dict[str, Any] = {
        "model": GEMINI_MODEL,
        "input": payload,
        "tools": tools,
        "generation_config": {"thinking_level": GEMINI_THINKING_LEVEL},
    }
    if previous_id is None:
        request["system_instruction"] = system_instruction
    else:
        request["previous_interaction_id"] = previous_id
    for attempt in range(1, MAX_RATE_LIMIT_ATTEMPTS + 1):
        try:
            return client.interactions.create(**request)
        except Exception as error:
            if not is_rate_limit_error(error) or attempt == MAX_RATE_LIMIT_ATTEMPTS:
                raise
            delay = _retry_delay(str(error))
            print(f"    rate limited, retrying in {delay:.0f}s (attempt {attempt})")
            time.sleep(delay)
    raise RuntimeError("exhausted Gemini retry attempts")


def _function_calls(interaction: Any) -> list[Any]:
    """Every function_call step the model emitted on this lap."""
    return [
        step
        for step in (interaction.steps or [])
        if getattr(step, "type", None) == "function_call"
    ]


async def run_agent(
    request: str,
    config: dict[str, dict[str, Any]],
    generate: Callable[..., Any] = _gemini_step,
    max_iterations: int = MAX_ITERATIONS,
    max_tokens: int = MAX_TOKENS,
    max_cost_usd: float = MAX_COST_USD,
    max_wall_clock_seconds: float = MAX_WALL_CLOCK_SECONDS,
) -> dict[str, Any]:
    """Connect, discover, then loop until the model answers or a budget stops it."""
    started = time.monotonic()
    calls_made: list[dict[str, Any]] = []
    log: list[str] = []
    laps = 0
    input_tokens = output_tokens = 0
    stop_reason = "completed"
    answer = ""

    async with connect(config) as hub:
        specs = hub.function_specs()
        instruction = build_instruction(hub)
        for server, tools in hub.tools_list.items():
            log.append(f"discovered {server}: {[tool['name'] for tool in tools]}")
        payload: Any = request
        previous_id: str | None = None

        while True:
            elapsed = time.monotonic() - started
            cost = modelled_cost(input_tokens, output_tokens)
            if laps >= max_iterations:
                stop_reason = "budget:max_iterations"
            elif input_tokens + output_tokens >= max_tokens:
                stop_reason = "budget:max_tokens"
            elif cost >= max_cost_usd:
                stop_reason = "budget:max_cost"
            elif elapsed >= max_wall_clock_seconds:
                stop_reason = "budget:wall_clock"
            if stop_reason != "completed":
                log.append(f"STOP {stop_reason} after {laps} laps")
                break

            laps += 1
            # The model call is blocking; off the event loop, the stdio readers keep running.
            interaction = await asyncio.to_thread(
                generate, instruction, payload, previous_id, specs
            )
            usage = getattr(interaction, "usage", None)
            if usage is not None:
                input_tokens += usage.total_input_tokens or 0
                output_tokens += usage.total_output_tokens or 0

            calls = _function_calls(interaction)
            if not calls:
                answer = interaction.output_text or ""
                log.append(f"lap {laps}: stopped calling tools")
                break

            results: list[dict[str, Any]] = []
            for call in calls:
                arguments = dict(call.arguments or {})
                server, is_error, text = await hub.call(call.name, arguments)
                calls_made.append(
                    {"lap": laps, "server": server, "tool": call.name, "arguments": arguments,
                     "is_error": is_error, "result": text}
                )
                log.append(
                    f"lap {laps}: [{server}] {call.name}({json.dumps(arguments)}) "
                    f"{'ERROR ' if is_error else ''}-> {' '.join(text.split())[:160]}"
                )
                results.append(
                    {
                        "type": "function_result",
                        "call_id": call.id,
                        "name": call.name,
                        "result": {"type": "text", "text": text},
                        "is_error": is_error,
                    }
                )
            payload = results
            previous_id = interaction.id

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request": request,
        "servers": {server: list(tools) for server, tools in _tool_names(hub).items()},
        "attached_resources": sorted(hub.attached),
        "calls": calls_made,
        "answer": answer,
        "laps": laps,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": modelled_cost(input_tokens, output_tokens),
        "latency_seconds": round(time.monotonic() - started, 3),
        "stop_reason": stop_reason,
        "log": log,
    }


def _tool_names(hub: ToolHub) -> dict[str, list[str]]:
    """Tool names per server, exactly as each server's tools/list returned them."""
    return {server: [tool["name"] for tool in tools] for server, tools in hub.tools_list.items()}


async def list_tools(config: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Connect and report what tools/list returned. No model call."""
    async with connect(config) as hub:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "servers": sorted(hub.sessions),
            "tool_count": len(hub.tool_owner),
            "tools_by_server": _tool_names(hub),
            "tools_list": hub.tools_list,
        }


def main() -> None:
    """Run one request, or only list the discovered tools."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", help="the recipe request")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--list-tools", action="store_true", help="discover tools and exit")
    parser.add_argument("--out", type=Path, help="write the --list-tools result as JSON here")
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--label", default="", help="tag stored with the trace")
    args = parser.parse_args()
    config = load_config(args.config)

    if args.list_tools:
        listing = asyncio.run(list_tools(config))
        for server, names in listing["tools_by_server"].items():
            print(f"{server}: {len(names)} tools {names}")
        print(f"total: {listing['tool_count']} tools from {len(listing['servers'])} server(s)")
        if args.out:
            args.out.write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")
        return

    if not args.request:
        parser.error("a request is required unless --list-tools is given")
    result = asyncio.run(run_agent(args.request, config))
    result["label"] = args.label
    with args.trace.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result) + "\n")
    for line in result["log"]:
        print("  " + line)
    print(f"\nstop_reason : {result['stop_reason']}")
    print(f"laps        : {result['laps']}")
    print(f"tokens      : {result['total_tokens']}")
    print(f"answer      : {result['answer']}")


if __name__ == "__main__":
    sys.exit(main())
