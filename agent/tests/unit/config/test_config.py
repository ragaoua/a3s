import pytest
from pydantic import ValidationError

import src.config as config_module
from src.config import (
    APIKeyAuth,
    OAuth2Auth,
    Config,
    get_config,
)


def _set_required_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_URI", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("MODEL", "abc")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("AGENT_DESCRIPTION", "test agent")
    monkeypatch.setenv("AGENT_INSTRUCTIONS", "Reply briefly.")
    monkeypatch.setenv("LISTEN_PORT", "1234")


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch):
    managed_keys = (
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
        "LISTEN_PORT",
        "AGENT_API_KEY",
        "OAUTH2_ISSUER_URL",
        "OAUTH2_JWKS_URL",
        "NO_AUTH",
        "MCP_SERVERS",
    )

    get_config.cache_clear()
    for key in managed_keys:
        monkeypatch.delenv(key, raising=False)

    yield

    get_config.cache_clear()


def test_config_loads_in_no_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")

    config = Config()

    assert config.auth is None


def test_config_loads_in_api_key_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("AGENT_API_KEY", "test-api-key")

    config = Config()

    assert isinstance(config.auth, APIKeyAuth)
    assert config.auth.api_key == "test-api-key"


def test_config_loads_in_oauth2_mode_with_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("OAUTH2_ISSUER_URL", "https://issuer.example")
    monkeypatch.setenv("OAUTH2_JWKS_URL", "https://issuer.example/jwks")

    config = Config()

    assert isinstance(config.auth, OAuth2Auth)
    assert config.auth.oauth2_issuer_url == "https://issuer.example"
    assert config.auth.oauth2_jwks_url == "https://issuer.example/jwks"


def test_config_loads_in_oauth2_mode_without_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("OAUTH2_ISSUER_URL", "https://issuer.example")

    config = Config()

    assert isinstance(config.auth, OAuth2Auth)
    assert config.auth.oauth2_issuer_url == "https://issuer.example"
    assert config.auth.oauth2_jwks_url is None


@pytest.mark.parametrize(
    ("agent_api_key", "oauth2_issuer_url", "no_auth"),
    [
        ("test-api-key", "https://issuer.example", False),
        ("test-api-key", None, True),
        (None, "https://issuer.example", True),
    ],
)
def test_config_rejects_conflicting_auth_modes(
    monkeypatch: pytest.MonkeyPatch,
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    no_auth: bool,
) -> None:
    _set_required_base_env(monkeypatch)

    if agent_api_key is not None:
        monkeypatch.setenv("AGENT_API_KEY", agent_api_key)
    if oauth2_issuer_url is not None:
        monkeypatch.setenv("OAUTH2_ISSUER_URL", oauth2_issuer_url)
    if no_auth:
        monkeypatch.setenv("NO_AUTH", "1")

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


def test_config_accepts_uppercase_true_for_no_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "TRUE")

    config = Config()

    assert config.auth is None


@pytest.mark.parametrize("no_auth_value", ["0", "false"])
def test_config_requires_other_mode_when_no_auth_is_falsey(
    monkeypatch: pytest.MonkeyPatch,
    no_auth_value: str,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", no_auth_value)

    with pytest.raises(ValidationError):
        Config()  # pyright: ignore[reportUnusedCallResult]


@pytest.mark.parametrize("invalid_port", ["abc", "3.14", ""])
def test_config_rejects_invalid_listen_port(
    monkeypatch: pytest.MonkeyPatch,
    invalid_port: str,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("LISTEN_PORT", invalid_port)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("LISTEN_PORT",) for error in exc.value.errors())


@pytest.mark.parametrize(
    "env_key",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
    ],
)
def test_config_rejects_empty_required_string_fields(
    monkeypatch: pytest.MonkeyPatch,
    env_key: str,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv(env_key, "")

    with pytest.raises(ValidationError):
        Config()  # pyright: ignore[reportUnusedCallResult]


@pytest.mark.parametrize(
    "missing_env_key",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
        "LISTEN_PORT",
    ],
)
def test_config_raises_when_required_env_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    missing_env_key: str,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.delenv(missing_env_key)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == (missing_env_key,) for error in exc.value.errors())


def test_config_requires_uppercase_env_keys_with_case_sensitive_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("llm_api_uri", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("llm_api_key", "test-key")
    monkeypatch.setenv("model", "abc")
    monkeypatch.setenv("agent_name", "test-agent")
    monkeypatch.setenv("agent_description", "test agent")
    monkeypatch.setenv("agent_instructions", "Reply briefly.")
    monkeypatch.setenv("listen_port", "1234")
    monkeypatch.setenv("NO_AUTH", "1")

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("LLM_API_URI",) for error in exc.value.errors())


def test_config_mcp_servers_is_snapshot_at_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("MCP_SERVERS", "mcp://one")

    config = Config()
    monkeypatch.setenv("MCP_SERVERS", "mcp://two")

    assert config.mcp_servers == ["mcp://one"]


def test_config_new_instance_picks_up_updated_mcp_servers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("MCP_SERVERS", "mcp://one")
    first = Config()

    monkeypatch.setenv("MCP_SERVERS", "mcp://two")
    second = Config()

    assert first.mcp_servers == ["mcp://one"]
    assert second.mcp_servers == ["mcp://two"]


def test_config_raises_when_no_auth_mode_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


def test_get_config_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "true")

    first = get_config()
    second = get_config()

    assert first is second


def test_get_config_returns_new_instance_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")

    first = get_config()
    get_config.cache_clear()
    second = get_config()

    assert first is not second


def test_get_config_exits_when_config_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.delenv("LLM_API_URI")

    with pytest.raises(SystemExit) as exc:
        get_config()  # pyright: ignore[reportUnusedCallResult]

    assert exc.value.code == 1


def test_get_config_mcp_servers_respects_cache_until_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_base_env(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("MCP_SERVERS", "mcp://one")

    first = get_config()
    monkeypatch.setenv("MCP_SERVERS", "mcp://two")
    second = get_config()

    assert first is second
    assert second.mcp_servers == ["mcp://one"]

    get_config.cache_clear()
    third = get_config()
    assert third.mcp_servers == ["mcp://two"]
