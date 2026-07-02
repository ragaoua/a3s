import json
import logging
from typing import override

from opentelemetry import trace
from pydantic import JsonValue

from src.config.types import LoggingConfig


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, JsonValue] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = trace.format_trace_id(span_context.trace_id)
            payload["span_id"] = trace.format_span_id(span_context.span_id)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


class PlainTextFormatter(logging.Formatter):
    """Render log records as a single human-readable line."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        line = f"{self.formatTime(record)} {record.levelname} [{record.name}]"

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            trace_id = trace.format_trace_id(span_context.trace_id)
            span_id = trace.format_span_id(span_context.span_id)
            line = f"{line} [trace_id={trace_id} span_id={span_id}]"

        line = f"{line} {record.getMessage()}"

        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"

        return line


def setup_logging(logging_config: LoggingConfig) -> None:
    if logging_config.format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainTextFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Reconfigure the root logger from scratch so repeated calls
    # don't stack duplicate handlers.
    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.setLevel(logging_config.level)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
