"""Tracer setup: OTLP/HTTP export to Langfuse Cloud.

Why OTLP and not the Langfuse SDK: the export target is just an OTLP
endpoint with basic auth. If Langfuse Cloud is ever replaced (self-hosted
Langfuse, Jaeger, Azure Monitor), only this module changes — no agent code,
no decorators, no attribute names. That migration cost asymmetry is the core
argument of ADR-0001.
"""

import base64
from importlib.metadata import version

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from aep.config import Settings

SERVICE_NAME = "agent-eval-platform"

_provider: TracerProvider | None = None


def init_tracing(settings: Settings) -> trace.Tracer:
    """Configure the global tracer provider once and return a tracer.

    Idempotent: repeated calls (e.g. from tests and the CLI in one process)
    reuse the first provider instead of stacking exporters, which would
    duplicate every span in Langfuse.
    """
    global _provider
    if _provider is None:
        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}"},
        )
        _provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": SERVICE_NAME,
                    "service.version": version("aep"),
                }
            )
        )
        _provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(_provider)
    return trace.get_tracer(SERVICE_NAME)


def flush() -> None:
    """Force-export pending spans.

    The batch processor exports on a timer; short-lived scripts (the runner,
    the example SUT) exit before the timer fires and would silently lose
    their traces without this.
    """
    if _provider is not None:
        _provider.force_flush()
