"""Pantry-to-Plate: a local web app over the integrated system.

    python ui.py --key 5          # prints its address, e.g. http://127.0.0.1:54814

Seven screens. "Ask" runs the full agent through pantry.answer(), exactly as `pantry.py ask`
does (agent loop, MCP tools, trace log, PII line). The other six call the same tool functions
the agent uses, directly and with no model: Recipes, Allergen check, Scale, Safe temperatures,
Swaps and History. So they are instant, free, exact, and keep working when the API quota is
spent.

Standard library only. Listens on 127.0.0.1 and refuses foreign Host and Origin headers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import pantry
import pantry_server
import tools
from capstone_corpus import CARDS_DIR, load_cards, safety_chart

PROJECT_DIR = Path(__file__).parent
PAGE = PROJECT_DIR / "ui" / "index.html"
HOST, PORT = "127.0.0.1", 8765
RESULT_PREVIEW_CHARS = 600
MAX_BODY_BYTES = 16_384
MAX_TEXT_CHARS = 120       # for a food name or ingredient on the tool screens
HISTORY_LIMIT = 50
RATE_LIMIT = 10            # questions per minute on Ask; each one costs 2-4 model calls
RATE_WINDOW_SECONDS = 60.0
TOOL_RATE_LIMIT = 120      # the tool screens make no model calls; this only stops a runaway loop
# The page is one self-contained file: nothing may load from, post to, or frame it from elsewhere.
SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
                                "style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
RECIPE_IDS = sorted({card["recipe_id"] for card in load_cards().values()})
VERSIONS = ["current", "original", "reformulated-2025"]


class BadRequest(ValueError):
    """An input the app refuses, with a message the page can show."""


class RateLimiter:
    """At most `limit` events in any sliding window of `window` seconds."""

    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW_SECONDS) -> None:
        self.limit, self.window, self.events = limit, window, deque()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        """Record one event if the window has room."""
        now = time.monotonic()
        with self.lock:
            while self.events and now - self.events[0] > self.window:
                self.events.popleft()
            if len(self.events) >= self.limit:
                return False
            self.events.append(now)
            return True


def make_server(port: int) -> ThreadingHTTPServer:
    """Bind on localhost (falling back to a free port) and attach the host list and limiters."""
    try:
        server = ThreadingHTTPServer((HOST, port), Handler)
    except OSError:
        # The port is taken (on this machine 8765 belongs to another app): let the OS pick one.
        server = ThreadingHTTPServer((HOST, 0), Handler)
    bound = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}
    server.limiter = RateLimiter()
    server.tool_limiter = RateLimiter(TOOL_RATE_LIMIT)
    return server


# --- input validation: the MCP schema does not apply when the tools are called directly ---

def _recipe(body: dict[str, Any]) -> str:
    recipe_id = body.get("recipe_id")
    if recipe_id not in RECIPE_IDS:
        raise BadRequest(f"recipe_id must be one of {RECIPE_IDS}")
    return recipe_id


def _allergens(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or any(a not in tools.AVOIDABLE for a in value):
        raise BadRequest(f"choose one or more of {tools.AVOIDABLE}")
    return sorted(set(value))


def _text(body: dict[str, Any], key: str) -> str:
    text = str(body.get(key, "")).strip()
    if not text or len(text) > MAX_TEXT_CHARS:
        raise BadRequest(f"{key} must be 1 to {MAX_TEXT_CHARS} characters")
    return text


def api_check(body: dict[str, Any]) -> dict[str, Any]:
    """Allergen check against the declaration field, by exact match. No model."""
    version = body.get("version", "current")
    if version not in VERSIONS:
        raise BadRequest(f"version must be one of {VERSIONS}")
    return pantry_server.check_allergens(_recipe(body), _allergens(body.get("avoid")), None, version)


def api_scale(body: dict[str, Any]) -> dict[str, Any]:
    """Scale the current version; times are returned unchanged. No model."""
    try:
        target = int(body.get("target_yield"))
    except (TypeError, ValueError):
        raise BadRequest("target_yield must be a whole number") from None
    if not 1 <= target <= tools.MAX_TARGET_SERVINGS:
        raise BadRequest(f"target_yield must be 1 to {tools.MAX_TARGET_SERVINGS}")
    return pantry_server.scale_recipe(_recipe(body), target, None)


def api_temperature(body: dict[str, Any]) -> dict[str, Any]:
    """Safe-temperature chart lookup; an unknown food is refused, never guessed. No model."""
    return pantry_server.safe_temperature(_text(body, "item"), None)


def api_substitute(body: dict[str, Any]) -> dict[str, Any]:
    """The test kitchen's substitution table, with the swap's own allergens. No model."""
    avoid = body.get("avoid")
    if avoid not in tools.AVOIDABLE:
        raise BadRequest(f"avoid must be one of {tools.AVOIDABLE}")
    return pantry_server.substitute_ingredient(_text(body, "ingredient"), avoid, None)


TOOL_ROUTES: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "/api/check": api_check, "/api/scale": api_scale,
    "/api/temperature": api_temperature, "/api/substitute": api_substitute,
}


# --- read-only data for the screens ---

def recipes() -> list[dict[str, Any]]:
    """Every card version with its declarations, current versions first."""
    out = []
    for card in load_cards().values():
        out.append({key: card[key] for key in ("key", "recipe_id", "version", "status", "title",
                                               "allergens", "may_contain", "yield_qty", "yield_unit",
                                               "times")} | {"file": Path(card["source_file"]).name})
    return sorted(out, key=lambda c: (c["recipe_id"], c["status"] != "current"))


def meta() -> dict[str, Any]:
    """What the screens need for their pickers."""
    return {"model": pantry.MODEL, "pipeline": pantry.PIPELINE_VERSION, "prompt": pantry.PROMPT_VERSION,
            "recipe_ids": RECIPE_IDS, "allergens": list(tools.AVOIDABLE), "versions": VERSIONS,
            "max_target": tools.MAX_TARGET_SERVINGS,
            "chart": safety_chart(),
            "substitutions": [{k: e[k] for k in ("ingredient", "avoid", "substitute", "contains", "source")}
                              for e in tools.SUBSTITUTIONS]}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def history() -> list[dict[str, Any]]:
    """The most recent requests from the PII-safe log: redacted questions only."""
    rows = _jsonl(pantry.REQUEST_LOG)[-HISTORY_LIMIT:]
    keep = ("trace_id", "timestamp", "question_redacted", "allergen_verdict", "pipeline_version",
            "model", "latency_ms", "total_tokens", "cost_usd", "injection_flags")
    return [{k: row.get(k) for k in keep} for row in reversed(rows)]


def trace(trace_id: str) -> dict[str, Any] | None:
    """One request's spans on both sides of the MCP hop, from the PII-safe logs."""
    request = next((r for r in _jsonl(pantry.REQUEST_LOG) if r["trace_id"] == trace_id), None)
    if request is None:
        return None
    server = [s for s in _jsonl(pantry.SPAN_LOG) if s.get("trace_id") == trace_id]
    return {"request": {k: request.get(k) for k in ("trace_id", "timestamp", "question_redacted",
                                                    "allergen_verdict", "citations", "spans", "tool_calls",
                                                    "latency_ms", "total_tokens", "cost_usd", "model",
                                                    "pipeline_version", "injection_flags")},
            "server_spans": [{k: s.get(k) for k in ("span", "latency_ms", "timestamp")} for s in server]}


def view(record: dict[str, Any]) -> dict[str, Any]:
    """The parts of an answer record the Ask screen shows."""
    return {
        "trace_id": record["trace_id"],
        "answer": record["answer"],
        "allergen_verdict": record["allergen_verdict"],
        "swap_guard": record.get("swap_guard"),
        "contradiction_guard": bool(record.get("contradiction_guard")),
        "injection_flags": record.get("injection_flags", []),
        "citations": record["citations"],
        "citation_files": {c: Path(card["source_file"]).name for c in record["citations"]
                           if (card := load_cards().get(c.split("::")[0]))},
        "calls": [{"tool": c["tool"], "server": c["server"], "arguments": c["arguments"],
                   "is_error": c["is_error"], "host_enforced": bool(c.get("host_enforced")),
                   "result": c["result"][:RESULT_PREVIEW_CHARS]}
                  for c in record["calls"]],
        "spans": record["spans"],
        "latency_ms": record["latency_ms"],
        "total_tokens": record["total_tokens"],
        "cost_usd": record["cost_usd"],
        "model": record["model"],
        "pipeline": record.get("pipeline_version"),
    }


class Handler(BaseHTTPRequestHandler):
    """The page, the cards, the read-only data, the tool screens, and Ask."""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self) -> bool:
        """Only our own address: a page on another site cannot reach us by DNS rebinding."""
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def _origin_ok(self) -> bool:
        """A POST from a page on another site is refused; a same-origin one, or curl, is allowed."""
        origin = self.headers.get("Origin")
        return origin is None or origin in {f"http://{host}" for host in self.server.allowed_hosts}

    def _json(self, status: int, payload: Any) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
        path = self.path.split("?")[0]
        if not self._host_ok():
            self._json(403, {"error": "unexpected Host header"})
        elif path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif path.startswith("/card/"):
            card = CARDS_DIR / Path(path[len("/card/"):]).name  # name only: no path escape
            if card.suffix == ".md" and card.exists():
                self._send(200, card.read_bytes(), "text/plain; charset=utf-8")
            else:
                self._json(404, {"error": "no such card"})
        elif path == "/api/meta":
            self._json(200, meta())
        elif path == "/api/recipes":
            self._json(200, recipes())
        elif path == "/api/history":
            self._json(200, history())
        elif path.startswith("/api/trace/"):
            found = trace(path[len("/api/trace/"):])
            self._json(200 if found else 404, found or {"error": "no such trace in this machine's log"})
        else:
            self._json(404, {"error": "not found"})

    def _read_json(self) -> dict[str, Any] | None:
        """Every POST: same-origin, JSON, bounded. Sends the error and returns None if not."""
        if not self._host_ok() or not self._origin_ok():
            self._json(403, {"error": "cross-site request refused"})
            return None
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self._json(415, {"error": "send JSON"})
            return None
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": f"request larger than {MAX_BODY_BYTES} bytes"})
            return None
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return None
        if not isinstance(body, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return None
        return body

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in TOOL_ROUTES:
            body = self._read_json()
            if body is None:
                return
            if not self.server.tool_limiter.allow():
                self._json(429, {"error": "too many requests; wait a moment"})
                return
            try:
                self._json(200, TOOL_ROUTES[path](body))
            except BadRequest as error:
                self._json(400, {"error": str(error)})
            return
        if path != "/api/ask":
            self._json(404, {"error": "not found"})
            return
        body = self._read_json()
        if body is None:
            return
        if not self.server.limiter.allow():
            self._json(429, {"error": f"at most {RATE_LIMIT} questions a minute; wait a moment"})
            return
        question = str(body.get("question", "")).strip()
        if not question:
            self._json(400, {"error": "ask a question"})
            return
        try:
            record = asyncio.run(pantry.answer(question))
        except Exception as error:
            if pantry.is_quota_error(error):
                self._json(429, {"error": f"Model quota refused ({pantry.MODEL}). The other tabs still "
                                          "work; restart with another --key for Ask."})
                return
            # Details stay in the terminal; the page gets a generic message.
            print(f"  error: {type(error).__name__}")
            self._json(500, {"error": "Something went wrong answering that. See the terminal."})
            return
        self._json(200, view(record))

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: one line per request, never the question (health data)."""
        print(f"  {self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")


def main() -> None:
    """Serve the app on localhost."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot to use for Ask")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
    if name in os.environ:
        os.environ["GEMINI_API_KEY"] = os.environ[name]
    else:
        print(f"  note: {name} is not set; Ask will fail, but every other tab works without a key.")
    server = make_server(args.port)
    port = server.server_address[1]
    print(f"Culinary Bot Studio (Pantry-to-Plate) on http://{HOST}:{port}  (model {pantry.MODEL}, pipeline "
          f"{pantry.PIPELINE_VERSION}, key slot {args.key}). Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
