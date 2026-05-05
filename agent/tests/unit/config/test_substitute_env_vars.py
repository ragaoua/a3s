import pytest
from pydantic import ValidationError

from src.config.config import substitute_env_vars


def test_substitute_env_vars_replaces_exact_placeholders_recursively() -> None:
    env = {
        "MODEL_NAME": "gpt-4.1-mini",
        "API_KEY": "super-secret",
        "HOSTNAME": "example.com",
    }

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

    assert substitute_env_vars(config, env=env) == {
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


def test_substitute_env_vars_leaves_partial_placeholders_unchanged() -> None:
    env: dict[str, str] = {}

    config = {
        "baseUrl": "https://${HOSTNAME}/v1",
        "relativePath": "${HOSTNAME}/v1",
        "message": "prefix ${HOSTNAME} suffix",
        "servers": ["api/${HOSTNAME}", {"value": "plain-text"}],
    }

    assert substitute_env_vars(config, env=env) == config


def test_substitute_env_vars_does_not_re_resolve_substituted_values() -> None:
    """A substituted value containing `${...}` is returned literally; no second pass."""
    env = {"OUTER": "${INNER}", "INNER": "should-not-appear"}

    assert substitute_env_vars({"value": "${OUTER}"}, env=env) == {"value": "${INNER}"}


def test_substitute_env_vars_raises_for_missing_or_empty_env_vars() -> None:
    env = {"EMPTY_TOKEN": ""}

    config = {
        "auth": {"apiKey": "${MISSING_API_KEY}"},
        "servers": [{"token": "${EMPTY_TOKEN}"}],
    }

    with pytest.raises(ValidationError) as exc_info:
        substitute_env_vars(config, env=env)  # pyright: ignore[reportUnusedCallResult]

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
