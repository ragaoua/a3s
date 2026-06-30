import logging
import os
import sys
from typing import Any

from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span

from src.config import Config

logger = logging.getLogger(__name__)

_TELEMETRY_ENABLED_ENV_VAR = "A3S_OTEL_ENABLED"


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def setup_telemetry(config: Config) -> None:
    if not _is_truthy(os.environ.get(_TELEMETRY_ENABLED_ENV_VAR)):
        logger.debug(
            "OpenTelemetry disabled. Set %s=true to enable console tracing.",
            _TELEMETRY_ENABLED_ENV_VAR,
        )
        return


    tracer_provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "a3s",
                "a3s.agent.name": config.agent.name,
            }
        )
    )
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stderr))
    )
    trace.set_tracer_provider(tracer_provider)

    GoogleADKInstrumentor().instrument()

    HTTPXClientInstrumentor().instrument()

    def server_request_hook(span: Span, scope: dict[str, Any]) -> None:
        span.set_attribute("a3s.agent.name", config.agent.name)
        # span.set_attribute("a3s.auth.mode", _AUTH_MODE)

    StarletteInstrumentor().instrument(server_request_hook=server_request_hook)

    logger.info("OpenTelemetry console tracing enabled on stderr")
