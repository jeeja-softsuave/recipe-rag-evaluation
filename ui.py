"""A small local web UI over the same entry point: pantry.answer().

    python ui.py --key 5          # then open http://127.0.0.1:8765

Standard library only. Every question still goes through the agent loop, the MCP servers,
the trace log and the PII line exactly as `pantry.py ask` does; this file only renders the
record. It listens on 127.0.0.1, so it is reachable from this machine only.
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
from typing import Any

import pantry
from capstone_corpus import CARDS_DIR, load_cards

PROJECT_DIR = Path(__file__).parent
PAGE = PROJECT_DIR / "ui" / "index.html"
HOST, PORT = "127.0.0.1", 8765
RESULT_PREVIEW_CHARS = 600
MAX_BODY_BYTES = 16_384
RATE_LIMIT = 10            # questions per minute; each one costs 2-4 model calls
RATE_WINDOW_SECONDS = 60.0
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
    """Bind on localhost (falling back to a free port) and attach the host list and limiter."""
    try:
        server = ThreadingHTTPServer((HOST, port), Handler)
    except OSError:
        # The port is taken (on this machine 8765 belongs to another app): let the OS pick one.
        server = ThreadingHTTPServer((HOST, 0), Handler)
    bound = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}
    server.limiter = RateLimiter()
    return server


def view(record: dict[str, Any]) -> dict[str, Any]:
    """The parts of an answer record the page shows."""
    return {
        "trace_id": record["trace_id"],
        "answer": record["answer"],
        "allergen_verdict": record["allergen_verdict"],
        "swap_guard": record.get("swap_guard"),
        "citations": record["citations"],
        "citation_files": {c: Path(card["source_file"]).name for c in record["citations"]
                           if (card := load_cards().get(c.split("::")[0]))},
        "calls": [{"tool": c["tool"], "server": c["server"], "arguments": c["arguments"],
                   "is_error": c["is_error"], "result": c["result"][:RESULT_PREVIEW_CHARS]}
                  for c in record["calls"]],
        "spans": record["spans"],
        "latency_ms": record["latency_ms"],
        "total_tokens": record["total_tokens"],
        "cost_usd": record["cost_usd"],
        "model": record["model"],
        "pipeline": record.get("pipeline_version"),
    }


class Handler(BaseHTTPRequestHandler):
    """GET / the page, GET /card/<file> a recipe card, POST /api/ask a question."""

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

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
        if not self._host_ok():
            self._json(403, {"error": "unexpected Host header"})
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/card/"):
            card = (CARDS_DIR / Path(self.path[len("/card/"):]).name)  # name only: no path escape
            if card.suffix == ".md" and card.exists():
                self._send(200, card.read_bytes(), "text/plain; charset=utf-8")
            else:
                self._json(404, {"error": "no such card"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/ask":
            self._json(404, {"error": "not found"})
            return
        if not self._host_ok() or not self._origin_ok():
            self._json(403, {"error": "cross-site request refused"})
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self._json(415, {"error": "send JSON"})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": f"request larger than {MAX_BODY_BYTES} bytes"})
            return
        if not self.server.limiter.allow():
            self._json(429, {"error": f"at most {RATE_LIMIT} questions a minute; wait a moment"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return
        question = str(body.get("question", "")).strip()
        if not question:
            self._json(400, {"error": "ask a question"})
            return
        try:
            record = asyncio.run(pantry.answer(question))
        except Exception as error:
            if pantry.is_quota_error(error):
                self._json(429, {"error": f"Model quota refused ({pantry.MODEL}). Restart with another --key."})
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
    """Serve the UI on localhost."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot to use")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
    os.environ["GEMINI_API_KEY"] = os.environ[name]
    server = make_server(args.port)
    port = server.server_address[1]
    print(f"Pantry-to-Plate UI on http://{HOST}:{port}  (model {pantry.MODEL}, pipeline "
          f"{pantry.PIPELINE_VERSION}, key slot {args.key}). Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
