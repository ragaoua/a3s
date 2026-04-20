import logging
import os
import sys
from threading import Lock

from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span
from opentelemetry.trace import SpanKind
from opentelemetry.trace import Status
from opentelemetry.trace import StatusCode
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import Config

logger = logging.getLogger(__name__)

_TELEMETRY_ENABLED_ENV_VAR = "A3S_OTEL_ENABLED"
_TRACER_NAME = "a3s.agent"
_TELEMETRY_LOCK = Lock()
_HTTPX_INSTRUMENTED = False
_TRACER_PROVIDER: TracerProvider | None = None


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def get_tracer(name: str = _TRACER_NAME):
    return trace.get_tracer(name)


def record_span_exception(span: Span, error: BaseException) -> None:
    if not span.is_recording():
        return

    span.record_exception(error)
    span.set_attribute("error.type", type(error).__name__)
    span.set_status(Status(StatusCode.ERROR, str(error)))


def set_current_span_attribute(name: str, value) -> None:
    if value is None:
        return

    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(name, value)


class TracingMiddleware:
    def __init__(self, app: ASGIApp, *, agent_name: str, auth_mode: str):
        self.app = app
        self.agent_name = agent_name
        self.auth_mode = auth_mode

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "HTTP")
        path = scope.get("path", "/")
        headers = {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        status_code: int | None = None

        with get_tracer(__name__).start_as_current_span(
            f"{method} {path}",
            context=propagate.extract(headers),
            kind=SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.request.method", method)
            span.set_attribute("url.path", path)
            span.set_attribute("a3s.agent.name", self.agent_name)
            span.set_attribute("a3s.auth.mode", self.auth_mode)

            query_string = scope.get("query_string", b"")
            if query_string:
                span.set_attribute("url.query", query_string.decode("latin-1"))

            http_version = scope.get("http_version")
            if http_version is not None:
                span.set_attribute("network.protocol.version", http_version)

            client = scope.get("client")
            if client and client[0] is not None:
                span.set_attribute("client.address", client[0])

            server = scope.get("server")
            if server and server[0] is not None:
                span.set_attribute("server.address", server[0])
                if server[1] is not None:
                    span.set_attribute("server.port", server[1])

            async def send_wrapper(message: Message) -> None:
                nonlocal status_code

                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    span.set_attribute("http.response.status_code", status_code)

                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as error:
                record_span_exception(span, error)
                raise

            route = scope.get("route")
            route_path = getattr(route, "path", None)
            if route_path:
                span.set_attribute("http.route", route_path)

            if status_code is not None and status_code >= 500:
                span.set_status(Status(StatusCode.ERROR))


def setup_telemetry(config: Config) -> None:
    if not _is_truthy(os.environ.get(_TELEMETRY_ENABLED_ENV_VAR)):
        logger.debug(
            "OpenTelemetry disabled. Set %s=true to enable console tracing.",
            _TELEMETRY_ENABLED_ENV_VAR,
        )
        return

    global _HTTPX_INSTRUMENTED, _TRACER_PROVIDER

    with _TELEMETRY_LOCK:
        if _TRACER_PROVIDER is not None:
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

        if not _HTTPX_INSTRUMENTED:
            HTTPXClientInstrumentor().instrument()
            _HTTPX_INSTRUMENTED = True

        _TRACER_PROVIDER = tracer_provider

    logger.info("OpenTelemetry console tracing enabled on stderr")
