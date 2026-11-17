"""OpenTelemetry tracing setup.

Tracing is disabled by default; the exporter only runs when TRACING_ENABLED=true.
All standard OTEL_* environment variables (endpoint, service name, BSP limits)
are honoured by the SDK/exporter.
"""
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    SERVICE_VERSION,
    OTELResourceDetector,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import settings

_tracer = trace.get_tracer("openassassin")
_provider: TracerProvider | None = None


def setup_tracing(app) -> None:
    global _provider, _tracer
    if not settings.tracing_enabled or _provider is not None:
        return

    resource = Resource.create({
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "openassassin-backend"),
        SERVICE_VERSION: settings.app_version,
    }).merge(OTELResourceDetector().detect())

    provider = TracerProvider(resource=resource)
    # HTTP/protobuf avoids gRPC native deps on alpine. Unit is seconds in this exporter.
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(timeout=5)))
    trace.set_tracer_provider(provider)
    _provider = provider
    _tracer = trace.get_tracer("openassassin")

    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

    # Added after AuditMiddleware so the OTel ASGI middleware is outermost and
    # the audit middleware can read the request's server span.
    FastAPIInstrumentor.instrument_app(app, excluded_urls=r"/api/health")
    HTTPXClientInstrumentor().instrument(request_hook=_redact_httpx_query)


def shutdown_tracing() -> None:
    global _provider
    provider, _provider = _provider, None
    if provider is not None:
        provider.shutdown()


def current_trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid or not ctx.trace_flags.sampled:
        return ""
    return format(ctx.trace_id, "032x")


@contextmanager
def job_span(name: str, attributes: dict | None = None):
    with _tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span


def _redact_httpx_query(span, request) -> None:
    """Strip user-controlled query strings before they reach Jaeger."""
    url = str(request.url)
    if "?" not in url:
        return
    clean = url.split("?", 1)[0]
    span.set_attribute("url.full", clean)
    span.set_attribute("http.url", clean)
    span.set_attribute("url.query", "")
