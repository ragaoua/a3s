import importlib
import logging
import sys
from collections.abc import Iterator

import pytest

from src.loggingManager import LoggingConfig, LoggingManager

JSON_FORMAT = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
PLAIN_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


@pytest.fixture(autouse=True)
def reset_logging_state() -> Iterator[None]:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    LoggingManager._instance = None
    for handler in original_handlers:
        root_logger.removeHandler(handler)

    yield

    LoggingManager._instance = None
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        if handler not in original_handlers:
            handler.close()

    root_logger.setLevel(original_level)
    for handler in original_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)


@pytest.mark.parametrize(
    ("log_format", "expected_format"),
    [
        ("json", JSON_FORMAT),
        ("plain", PLAIN_FORMAT),
    ],
)
def test_logging_manager_applies_requested_log_format(
    monkeypatch: pytest.MonkeyPatch,
    log_format: str,
    expected_format: str,
) -> None:
    monkeypatch.setenv("LOG_FORMAT", log_format)

    LoggingManager()  # pyright: ignore[reportUnusedCallResult]
    root_logger = logging.getLogger()

    formatter = root_logger.handlers[0].formatter
    assert formatter is not None
    assert formatter._fmt == expected_format


def test_logging_manager_initializes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    basic_config_calls = 0
    original_basic_config = logging.basicConfig

    def spy_basic_config(*args, **kwargs) -> None:
        nonlocal basic_config_calls
        basic_config_calls += 1
        original_basic_config(*args, **kwargs)

    monkeypatch.setattr(logging, "basicConfig", spy_basic_config)

    manager_one = LoggingManager()
    manager_two = LoggingManager()

    assert manager_one is manager_two
    assert basic_config_calls == 1


def test_logging_manager_reads_log_settings_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "json")

    manager = LoggingManager()
    module_logger = manager.get_logger(__name__)
    root_logger = logging.getLogger()

    assert root_logger.level == logging.DEBUG
    assert module_logger.isEnabledFor(logging.DEBUG)
    assert root_logger.handlers
    formatter = root_logger.handlers[0].formatter
    assert formatter is not None
    assert formatter._fmt == JSON_FORMAT


def test_logging_manager_propagates_settings_to_new_loggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LOG_FORMAT", "plain")

    LoggingManager()

    downstream_logger = logging.getLogger("downstream.component")

    assert downstream_logger.getEffectiveLevel() == logging.WARNING
    assert downstream_logger.isEnabledFor(logging.WARNING)
    assert not downstream_logger.isEnabledFor(logging.INFO)
