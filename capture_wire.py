"""Capture the raw JSON-RPC exchange with one configured MCP server. No SDK client.

Spawns the server exactly as mcp_config.json says, writes newline-delimited JSON-RPC to
its stdin and records every line it writes back, verbatim. The sequence is the one every
host runs: initialize -> notifications/initialized -> tools/list -> tools/call.
No model is involved anywhere in this script.

    python capture_wire.py ingredient-db lookup_nutrition '{"ingredient": "urad dal"}'
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from mcp_agent import DEFAULT_CONFIG, PROJECT_DIR, load_config

PROTOCOL_VERSION = "2025-11-25"
CLIENT_INFO = {"name": "capture-wire", "version": "1.0"}


def exchange(process: subprocess.Popen, message: dict[str, Any], record: list) -> None:
    """Send one message; if it is a request, read and record its response."""
    line = json.dumps(message)
    record.append({"direction": "client -> server", "raw": line})
    process.stdin.write(line + "\n")
    process.stdin.flush()
    if "id" not in message:
        return
    reply = process.stdout.readline().rstrip("\n")
    record.append({"direction": "server -> client", "raw": reply})


def main() -> None:
    """Run the four-message sequence against one server and save the transcript."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", help="server name as it appears in mcp_config.json")
    parser.add_argument("tool")
    parser.add_argument("arguments", help="tool arguments as a JSON object")
    parser.add_argument("--out", type=Path, default=PROJECT_DIR / "wire_raw.json")
    args = parser.parse_args()

    entry = load_config(DEFAULT_CONFIG)[args.server]
    # Windows does not resolve a relative executable against cwd, so resolve it here.
    local = PROJECT_DIR / entry["command"]
    command = str(local) if local.exists() else entry["command"]
    process = subprocess.Popen(
        [command, *entry.get("args", [])],
        cwd=PROJECT_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
    )
    record: list[dict[str, str]] = []
    try:
        exchange(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO,
        }}, record)
        exchange(process, {"jsonrpc": "2.0", "method": "notifications/initialized"}, record)
        exchange(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, record)
        exchange(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": args.tool, "arguments": json.loads(args.arguments),
        }}, record)
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for item in record:
        print(f"{item['direction']}: {item['raw']}")


if __name__ == "__main__":
    main()
