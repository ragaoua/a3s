import pytest
from pydantic import ValidationError

from src.config.config import substitute_env_vars


def test_substitute_env_vars_replaces_exact_placeholders_recursively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_NAME", "gpt-4.1-mini")
    monkeypatch.setenv("API_KEY", "super-secret")
    monkeypatch.setenv("HOSTNAME", "example.com")

    config = {
        "llm": {
            "model": "${MODEL_NAME}",
            "apiKey": "${API_KEY}",
        },
        "servers": [
            "${HOSTNAME}",
            {
                "port": 443,
                "enabled": True,
            },
        ],
    }

    assert substitute_env_vars(config) == {
        "llm": {
            "model": "gpt-4.1-mini",
            "apiKey": "super-secret",
        },
        "servers": [
            "example.com",
            {
                "port": 443,
                "enabled": True,
            },
        ],
    }


def test_substitute_env_vars_leaves_partial_placeholders_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HOSTNAME", raising=False)

    config = {
        "baseUrl": "https://${HOSTNAME}/v1",
        "relativePath": "${HOSTNAME}/v1",
        "message": "prefix ${HOSTNAME} suffix",
        "servers": ["api/${HOSTNAME}", {"value": "plain-text"}],
    }

    assert substitute_env_vars(config) == config


def test_substitute_env_vars_raises_for_missing_or_empty_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_API_KEY", raising=False)
    monkeypatch.setenv("EMPTY_TOKEN", "")

    config = {
        "auth": {"apiKey": "${MISSING_API_KEY}"},
        "servers": [{"token": "${EMPTY_TOKEN}"}],
    }

    with pytest.raises(ValidationError) as exc_info:
        substitute_env_vars(config)  # pyright: ignore[reportUnusedCallResult]

    assert [
        {
            "loc": error["loc"],
            "input": error["input"],
            "msg": error["msg"],
        }
        for error in exc_info.value.errors(include_url=False)
    ] == [
        {
            "loc": ("auth", "apiKey"),
            "input": "${MISSING_API_KEY}",
            "msg": "Value error, Environment variable 'MISSING_API_KEY' is not set or empty",
        },
        {
            "loc": ("servers", 0, "token"),
            "input": "${EMPTY_TOKEN}",
            "msg": "Value error, Environment variable 'EMPTY_TOKEN' is not set or empty",
        },
    ]
