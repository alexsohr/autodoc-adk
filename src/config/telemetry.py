"""OpenTelemetry and structured logging configuration.

MUST be called before any Google ADK imports - ADK auto-discovers
the global TracerProvider at import time.

Usage at application entry point::

    from src.config.telemetry import configure_telemetry
    configure_telemetry()

    # Now safe to import ADK
    from google.adk import ...
"""

from __future__ import annotations

import contextvars
import logging
import os
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pythonjsonlogger.json import JsonFormatter

# ---------------------------------------------------------------------------
# Correlation context - set by flows/tasks, read by CorrelationFilter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CorrelationContext:
    job_id: str = ""
    agent_name: str = ""
    task_name: str = ""


_correlation_ctx: contextvars.ContextVar[_CorrelationContext | None] = contextvars.ContextVar(
    "correlation_ctx",
    default=None,
)

_EMPTY_CONTEXT = _CorrelationContext()


def set_correlation_context(
    *,
    job_id: str | None = None,
    agent_name: str | None = None,
    task_name: str | None = None,
) -> None:
    """Update correlation fields available to all log records in the current context.

    Only provided (non-None) fields are changed; the rest keep their current value.
    """
    current = _correlation_ctx.get() or _EMPTY_CONTEXT
    _correlation_ctx.set(
        _CorrelationContext(
            job_id=job_id if job_id is not None else current.job_id,
            agent_name=agent_name if agent_name is not None else current.agent_name,
            task_name=task_name if task_name is not None else current.task_name,
        )
    )


# ---------------------------------------------------------------------------
# Logging filter that injects correlation + OTel fields
# ---------------------------------------------------------------------------


class CorrelationFilter(logging.Filter):
    """Injects ``job_id``, ``agent_name``, and ``task_name`` into every log record.

    Values come from the current :func:`set_correlation_context` call (via
    *contextvars*), defaulting to ``""`` when unset.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _correlation_ctx.get() or _EMPTY_CONTEXT
        record.job_id = ctx.job_id  # type: ignore[attr-defined]
        record.agent_name = ctx.agent_name  # type: ignore[attr-defined]
        record.task_name = ctx.task_name  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------

_configured = False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def configure_telemetry() -> None:
    """Set up OpenTelemetry tracing + JSON structured logging.

    Safe to call multiple times - subsequent calls are no-ops.

    Environment variables consumed:

    * ``OTEL_SERVICE_NAME`` - resource ``service.name`` (default ``autodoc-adk``)
    * ``APP_COMMIT_SHA`` - resource ``service.version`` (default ``unknown``)
    * ``OTEL_EXPORTER_OTLP_ENDPOINT`` - gRPC collector (default ``http://localhost:4317``)
    * ``LOG_LEVEL`` - root log level (default ``INFO``)
    """
    global _configured
    if _configured:
        return
    _configured = True

    # ── Tracing ──────────────────────────────────────────────────────────
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "autodoc-adk"),
            "service.version": os.getenv("APP_COMMIT_SHA", "unknown"),
        }
    )

    provider = TracerProvider(resource=resource)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # ── LoggingInstrumentor ──────────────────────────────────────────────
    # Injects otelTraceID / otelSpanID / otelServiceName into log records.
    LoggingInstrumentor().instrument(set_logging_format=False)

    # ── JSON structured logging ──────────────────────────────────────────
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(otelTraceID)s %(otelSpanID)s %(otelServiceName)s "
        "%(job_id)s %(agent_name)s %(task_name)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "otelTraceID": "trace_id",
            "otelSpanID": "span_id",
            "otelServiceName": "service",
        },
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)
