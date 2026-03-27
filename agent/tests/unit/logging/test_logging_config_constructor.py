import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

import src.loggingManager as logging_manager


class TestLoggingConfig(logging_manager.LoggingConfig):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )


def test_logging_config_uses_defaults_when_env_vars_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)

    config = TestLoggingConfig()  # pyright: ignore[reportCallIssue]

    assert config.LOG_LEVEL == "INFO"
    assert config.LOG_FORMAT == "plain"


@pytest.mark.parametrize("log_level", ["INFO", "DEBUG", "WARNING", "ERROR"])
@pytest.mark.parametrize("log_format", ["plain", "json"])
def test_logging_config_accepts_supported_values(
    monkeypatch: pytest.MonkeyPatch,
    log_level: str,
    log_format: str,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", log_level)
    monkeypatch.setenv("LOG_FORMAT", log_format)

    config = TestLoggingConfig()  # pyright: ignore[reportCallIssue]

    assert config.LOG_LEVEL == log_level
    assert config.LOG_FORMAT == log_format


def test_logging_config_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "TRACE")

    with pytest.raises(ValidationError) as exc:
        TestLoggingConfig()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == ("LOG_LEVEL",) for error in exc.value.errors())


def test_logging_config_rejects_invalid_log_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_FORMAT", "xml")

    with pytest.raises(ValidationError) as exc:
        TestLoggingConfig()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == ("LOG_FORMAT",) for error in exc.value.errors())


def test_logging_config_values_are_snapshot_at_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    config = TestLoggingConfig()  # pyright: ignore[reportCallIssue]
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    assert config.LOG_LEVEL == "INFO"


def test_logging_config_new_instance_picks_up_updated_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "plain")
    TestLoggingConfig()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "json")

    updated = TestLoggingConfig()  # pyright: ignore[reportCallIssue]

    assert updated.LOG_LEVEL == "DEBUG"
    assert updated.LOG_FORMAT == "json"


def test_logging_config_ignores_lowercase_env_vars_when_case_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    monkeypatch.setenv("log_level", "ERROR")
    monkeypatch.setenv("log_format", "json")

    config = TestLoggingConfig()  # pyright: ignore[reportCallIssue]

    assert config.LOG_LEVEL == "INFO"
    assert config.LOG_FORMAT == "plain"
