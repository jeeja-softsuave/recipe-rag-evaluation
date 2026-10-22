"""OpenTelemetry for the integrated system: the agent's spans and the MCP server's spans join one
OTel trace, carried across the MCP hop by a W3C traceparent in the request's _meta.

Exporters:
  always    logs/otel_spans.jsonl: one OTel span per line, readable with no collector running
  optional  OTLP over gRPC to OTEL_EXPORTER_OTLP_ENDPOINT, e.g. http://localhost:4317 for a local
            Arize Phoenix or any OpenTelemetry collector. Nothing leaves the machine unless set.

PII line: span attributes never carry the question or the answer. They carry ids, versions,
tool names, recipe ids, allergen categories, verdicts, token counts and cost.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

OTEL_FILE = Path(__file__).parent / "logs" / "otel_spans.jsonl"
_lock = threading.Lock()
_configured = False


class JsonlSpanExporter(SpanExporter):
    """Append each finished span as one JSON line: ids, timing, attributes, status."""

    def __init__(self, path: Path = OTEL_FILE) -> None:
        self.path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.path.parent.mkdir(exist_ok=True)
        with _lock, self.path.open("a", encoding="utf-8") as handle:
            for span in spans:
                handle.write(json.dumps(_as_dict(span), ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def _as_dict(span: ReadableSpan) -> dict[str, Any]:
    """The fields worth reading from one span."""
    context = span.get_span_context()
    return {
        "service": span.resource.attributes.get("service.name"),
        "name": span.name,
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
        "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
        "duration_ms": round((span.end_time - span.start_time) / 1e6, 1),
        "status": span.status.status_code.name,
        "attributes": dict(span.attributes or {}),
    }


def setup(service: str) -> trace.Tracer:
    """Configure the process-wide tracer provider once, and return a tracer."""
    global _configured
    if not _configured:
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter()))
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        atexit.register(provider.shutdown)
        _configured = True
    return trace.get_tracer(service)


def inject_context(meta: dict[str, Any]) -> dict[str, Any]:
    """Add the current span's W3C traceparent to an MCP _meta dict."""
    propagate.inject(meta)
    return meta


def extract_context(meta: dict[str, Any] | None) -> Any:
    """The parent context an MCP caller sent in _meta, or an empty one."""
    return propagate.extract(meta or {})
