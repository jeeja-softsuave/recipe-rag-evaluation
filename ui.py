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
import hashlib
import json
import os
import re
import secrets
import threading
from concurrent.futures import Future, ThreadPoolExecutor
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import fastpath
import pantry
import pantry_server
import tools
from capstone_corpus import CARDS_DIR, load_cards, safety_chart
from mcp_agent import connect, load_config

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
CACHE_TTL_SECONDS = 1800   # a repeated question within 30 minutes is answered from memory
CACHE_SIZE = 200
# Every reply within 15 s: an agent answer not ready after this long is replaced, for now, by the
# recipe facts the cards hold, and the page collects the full answer from /api/job/<id> later.
ANSWER_BUDGET_SECONDS = 13.0
JOB_TTL_SECONDS = 600
MAX_CONTEXT_CHARS = 500
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
    server.cache = AnswerCache()
    server.instant = True
    server.runner = None  # main() attaches an AgentRunner; tests answer per request
    server.budget = ANSWER_BUDGET_SECONDS
    server.jobs = {}      # job id -> (created, future, cache key question, mode)
    return server


class AnswerCache:
    """A repeated question is answered from memory. Memory only, never written to disk, because
    a question can carry health data; keyed by a hash of the normalised question."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS, size: int = CACHE_SIZE) -> None:
        self.ttl, self.size, self.items = ttl, size, {}
        self.lock = threading.Lock()

    @staticmethod
    def key(question: str) -> str:
        return hashlib.sha256(re.sub(r"[\s?!.,]+", " ", question.lower()).strip().encode()).hexdigest()

    def get(self, question: str) -> dict[str, Any] | None:
        with self.lock:
            hit = self.items.get(self.key(question))
            return hit[1] if hit and time.monotonic() - hit[0] < self.ttl else None

    def put(self, question: str, payload: dict[str, Any]) -> None:
        with self.lock:
            if len(self.items) >= self.size:
                self.items.pop(next(iter(self.items)))  # oldest first
            self.items[self.key(question)] = (time.monotonic(), payload)


class AgentRunner:
    """One event-loop thread that keeps the MCP servers connected for the app's lifetime, so an
    agent question does not pay ~4 s to start them and warm the retriever (measured)."""

    def __init__(self) -> None:
        self.loop, self.hub, self.ready = asyncio.new_event_loop(), None, threading.Event()
        threading.Thread(target=self.loop.run_until_complete, args=(self._hold(),), daemon=True).start()

    async def _hold(self) -> None:
        try:
            async with connect(load_config(pantry.CONFIG)) as hub:
                await pantry._call_tool(hub, "search_recipes", {"query": "idli batter"}, "t-warmup")
                self.hub = hub
                self.ready.set()
                await asyncio.Event().wait()  # held until the process exits
        finally:
            self.ready.set()

    def submit(self, question: str) -> Future:
        if not self.ready.wait(timeout=60) or self.hub is None:
            return submit_per_request(question)  # servers failed to start: per-question path
        return asyncio.run_coroutine_threadsafe(pantry.answer(question, hub=self.hub), self.loop)


_BACKGROUND = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent")


def submit_per_request(question: str) -> Future:
    """The agent on its own event loop, opening the MCP servers for this question only."""
    return _BACKGROUND.submit(lambda: asyncio.run(pantry.answer(question)))


def _mentions(error: BaseException, text: str) -> bool:
    """True when the error, or any error wrapped inside it (anyio nests them), mentions text."""
    if isinstance(error, BaseExceptionGroup):
        return any(_mentions(inner, text) for inner in error.exceptions)
    return text in str(error) or (error.__cause__ is not None and _mentions(error.__cause__, text))


def error_reply(error: BaseException) -> tuple[int, dict[str, str]]:
    """A plain message for the page; the details stay in the terminal."""
    if pantry.is_quota_error(error):
        return 429, {"error": f"Model quota refused ({pantry.MODEL}). The tool tabs still work; "
                              "restart with other --keys for Chat."}
    if _mentions(error, "free tier is not available"):
        return 503, {"error": "Google refused these Gemini keys: their projects have no free-tier access. "
                              "Enable billing on one project, or restart with keys that work. The tool tabs still work."}
    print(f"  error: {type(error).__name__}", flush=True)
    return 500, {"error": "Something went wrong answering that. See the terminal."}


def with_context(question: str, context: Any) -> str:
    """A follow-up ('what is the alternative?') carries the chat's previous question, so the agent
    and the guards both see the allergy and the recipe it refers to."""
    earlier = str(context or "").strip()[:MAX_CONTEXT_CHARS]
    return f"{question}\n\n(Earlier in this chat I asked: {earlier})" if earlier else question


def interim(question: str) -> dict[str, Any]:
    """What the app can say at once while the agent is still working: the declaration facts of
    every recipe the question names, straight from the cards. No verdict is drawn from them."""
    lowered = question.lower()
    named = sorted({rid for word, rid in pantry.RECIPE_WORDS.items() if re.search(rf"\b{word}s?\b", lowered)})
    cards = [c for c in load_cards().values() if c["recipe_id"] in named and c["status"] == "current"]
    return {"cards": [{"title": c["title"], "citation": c["key"], "allergens": c["allergens"],
                       "may_contain": c["may_contain"], "yield": f"{c['yield_qty']} {c['yield_unit']}",
                       "times": c["times"], "file": Path(c["source_file"]).name} for c in cards[:3]]}


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
        "route": "instant" if str(record.get("stop", "")).startswith("instant") else "agent",
        "cached": False,
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
        elif path.startswith("/api/job/"):
            self._job(path[len("/api/job/"):])
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
        question = str(body.get("question", "")).strip()
        mode = body.get("mode", "auto")
        if not question or mode not in ("auto", "agent"):
            self._json(400, {"error": "ask a question" if not question else "mode must be auto or agent"})
            return
        asked = with_context(question, body.get("context"))
        # Fastest first: a repeat from memory, then the tools alone, then the agent.
        # mode "agent" skips both, to show the full agent loop.
        if mode == "auto":
            if not self.server.tool_limiter.allow():
                self._json(429, {"error": "too many requests; wait a moment"})
                return
            if (cached := self.server.cache.get(asked)) is not None:
                self._json(200, {**cached, "cached": True})
                return
            if self.server.instant and (record := fastpath.answer(question)) is not None:
                payload = view(record)
                self.server.cache.put(asked, payload)
                self._json(200, payload)
                return
        if not self.server.limiter.allow():
            self._json(429, {"error": f"at most {RATE_LIMIT} questions a minute; wait a moment"})
            return
        runner = self.server.runner
        future = runner.submit(asked) if runner else submit_per_request(asked)
        try:
            record = future.result(timeout=self.server.budget)
        except TimeoutError:
            # Over budget: reply now with what the cards say, and let the page collect the rest.
            self._expire_jobs()
            job = secrets.token_urlsafe(12)
            self.server.jobs[job] = (time.monotonic(), future, asked, mode)
            self._json(202, {"pending": job, "interim": interim(asked), "budget_s": self.server.budget})
            return
        except Exception as error:
            self._json(*error_reply(error))
            return
        self._json(200, self._finish_answer(record, asked, mode))

    def _finish_answer(self, record: dict[str, Any], asked: str, mode: str) -> dict[str, Any]:
        payload = view(record)
        if mode == "auto" and not record["injection_flags"]:
            self.server.cache.put(asked, payload)
        return payload

    def _expire_jobs(self) -> None:
        now = time.monotonic()
        for job in [j for j, (created, *_) in self.server.jobs.items() if now - created > JOB_TTL_SECONDS]:
            self.server.jobs.pop(job, None)

    def _job(self, job: str) -> None:
        """GET /api/job/<id>: 202 while the agent works, then the answer once (the job is removed)."""
        entry = self.server.jobs.get(job)
        if entry is None:
            self._json(404, {"error": "no such answer pending (it may have expired)"})
            return
        _, future, asked, mode = entry
        if not future.done():
            self._json(202, {"pending": job})
            return
        self.server.jobs.pop(job, None)
        try:
            record = future.result()
        except Exception as error:
            self._json(*error_reply(error))
            return
        self._json(200, self._finish_answer(record, asked, mode))

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: one line per request, never the question (health data)."""
        print(f"  {self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")


def main() -> None:
    """Serve the app on localhost."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot to use for Ask")
    parser.add_argument("--keys", help="several slots to spread and hedge model calls over, e.g. 1,2,3,4,5")
    parser.add_argument("--hedge-after", type=float, default=pantry.HEDGE_AFTER_SECONDS,
                        help="seconds before a slow model call is re-sent on another key (0 = off)")
    parser.add_argument("--no-instant", action="store_true", help="send every question to the agent")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    slots = [int(s) for s in args.keys.split(",")] if args.keys else [args.key]
    names = [("GEMINI_API_KEY" if slot == 1 else f"GEMINI_API_KEY{slot}") for slot in slots]
    missing = [name for name in names if name not in os.environ]
    if missing:
        print(f"  note: {', '.join(missing)} not set; the agent will skip them. Every tool tab works without a key.")
    present = [name for name in names if name in os.environ]
    if present:
        os.environ["GEMINI_API_KEY"] = os.environ[present[0]]
        os.environ["GEMINI_KEY_POOL"] = ",".join(present)
    pantry.HEDGE_AFTER_SECONDS = args.hedge_after
    server = make_server(args.port)
    server.instant = not args.no_instant
    server.runner = AgentRunner()
    port = server.server_address[1]
    print(f"Culinary Bot Studio (Pantry-to-Plate) on http://{HOST}:{port}  (model {pantry.MODEL}, pipeline "
          f"{pantry.PIPELINE_VERSION}, key slots {','.join(map(str, slots))}, hedge after {args.hedge_after:g}s, "
          f"instant answers {'off' if args.no_instant else 'on'}). Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
