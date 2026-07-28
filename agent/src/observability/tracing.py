from contextlib import contextmanager
import logging
from collections.abc import Generator
from typing import Any

from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from src.config import Config

logger = logging.getLogger(__name__)


@contextmanager
def tracing_instrumentation(config: Config) -> Generator[None]:
    if not config.observability.tracing.enabled:
        logger.debug(
            "OpenTelemetry disabled. Set `observability.tracing.enabled: true` "
            "in the config to enable tracing.",
        )
        yield
        return

    tracer_provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "a3s",
                "a3s.agent.name": config.agent.name,
            }
        )
    )
    span_processor = BatchSpanProcessor(OTLPSpanExporter())
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Collect ADK spans such as `invocation`, `invoke_agent`, `call_llm`, and `execute_tool`
    GoogleADKInstrumentor().instrument()

    # Collect outbound HTTP spans for auth, MCP, and other `httpx` calls
    HTTPXClientInstrumentor().instrument()

    def server_request_hook(span: Span, scope: dict[str, Any]) -> None:
        span.set_attribute("a3s.agent.name", config.agent.name)

    # Collect request spans for incoming HTTP traffic
    StarletteInstrumentor().instrument(server_request_hook=server_request_hook)

    logger.info("OpenTelemetry tracing enabled (exporter: OTLP)")

    try:
        yield
    finally:
        # Flush and shut down the BatchSpanProcessor before the process
        # exits. It queues spans and exports them asynchronously, so any
        # spans still in the buffer are lost unless the provider is shut
        # down cleanly.
        tracer_provider.shutdown()
