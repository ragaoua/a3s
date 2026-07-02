import json
import logging
from typing import Any

from pydantic import JsonValue
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from src.config.types import LoggingConfig
from src.observability.logging import JsonFormatter, PlainTextFormatter, setup_logging


def _make_record(
    msg: str,
    *,
    level: int = logging.INFO,
    args: tuple[JsonValue, ...] = (),
    exc_info: Any = None,
) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def test_json_formatter_emits_valid_json_with_core_fields():
    record = _make_record("hello world")

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert "timestamp" in payload


def test_json_formatter_escapes_special_characters():
    # A message that would produce invalid JSON if spliced into a string template.
    record = _make_record('he said "hi"\nand a \\ backslash')

    # Must round-trip without raising.
    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == 'he said "hi"\nand a \\ backslash'


def test_json_formatter_interpolates_args():
    record = _make_record("server %s ready on %d", args=("mcp", 8080))

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "server mcp ready on 8080"


def test_json_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record("failed", level=logging.ERROR, exc_info=sys.exc_info())

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_formatter_omits_trace_ids_without_active_span():
    payload = json.loads(JsonFormatter().format(_make_record("no span")))

    assert "trace_id" not in payload
    assert "span_id" not in payload


def test_json_formatter_adds_trace_ids_under_active_span():
    tracer = TracerProvider().get_tracer(__name__)

    with tracer.start_as_current_span("unit-span"):
        span_context = trace.get_current_span().get_span_context()
        payload = json.loads(JsonFormatter().format(_make_record("with span")))

    assert payload["trace_id"] == trace.format_trace_id(span_context.trace_id)
    assert payload["span_id"] == trace.format_span_id(span_context.span_id)


def test_text_formatter_emits_core_fields():
    line = PlainTextFormatter().format(_make_record("hello world"))

    assert "INFO" in line
    assert "[test.logger]" in line
    assert line.endswith("hello world")


def test_text_formatter_interpolates_args():
    line = PlainTextFormatter().format(
        _make_record("server %s ready on %d", args=("mcp", 8080))
    )

    assert line.endswith("server mcp ready on 8080")


def test_text_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record("failed", level=logging.ERROR, exc_info=sys.exc_info())

    line = PlainTextFormatter().format(record)

    assert "failed" in line
    assert "ValueError: boom" in line


def test_text_formatter_omits_trace_ids_without_active_span():
    line = PlainTextFormatter().format(_make_record("no span"))

    assert "trace_id=" not in line
    assert "span_id=" not in line


def test_text_formatter_adds_trace_ids_under_active_span():
    tracer = TracerProvider().get_tracer(__name__)

    with tracer.start_as_current_span("unit-span"):
        span_context = trace.get_current_span().get_span_context()
        line = PlainTextFormatter().format(_make_record("with span"))

    assert f"trace_id={trace.format_trace_id(span_context.trace_id)}" in line
    assert f"span_id={trace.format_span_id(span_context.span_id)}" in line


@pytest.mark.parametrize("log_format", ["json", "plain"])
def test_setup_logging_installs_single_handler(log_format):
    setup_logging(LoggingConfig(level="DEBUG", format=log_format))
    setup_logging(LoggingConfig(level="DEBUG", format=log_format))

    root = logging.getLogger()

    assert len(root.handlers) == 1
    assert root.level == logging.DEBUG


def test_setup_logging_json_produces_parseable_output(capsys):
    setup_logging(LoggingConfig(level="INFO", format="json"))

    logging.getLogger("some.module").info('quote " and newline\n here')

    line = capsys.readouterr().err.strip()
    payload = json.loads(line)
    assert payload["message"] == 'quote " and newline\n here'
    assert payload["logger"] == "some.module"
