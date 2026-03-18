from pydantic_settings import SettingsConfigDict
import pytest
from pydantic import ValidationError

from src.config import (
    APIKeyAuth,
    OAuth2Auth,
    from_env,
)


# Load the module (not the class directly) to patch it, replacing
# it with TestConfig, so that other modules (namely, from_env)
# also get the patched Config
import src.config as config


class TestConfig(config.Config):
    model_config: SettingsConfigDict = SettingsConfigDict(env_file=None)


config.Config = TestConfig  # Patch config.Config
Config = config.Config


@pytest.fixture(autouse=True)
def clear_from_env_cache():
    from_env.cache_clear()


def _set_base_test_env_with(
    monkeypatch: pytest.MonkeyPatch,
    LLM_API_URI: str = "endpoint",
    LLM_API_KEY: str = "fakekey",
    MODEL: str = "mymodel",
    AGENT_NAME: str = "Cody",
    AGENT_DESCRIPTION: str = "A helpful coding assistant",
    AGENT_INSTRUCTIONS: str = "You are a coding agent. Use the tools provided to access the user's requests regarding coding tasks",
    LISTEN_PORT: str = "12345",
) -> None:
    monkeypatch.setenv("LLM_API_URI", LLM_API_URI)
    monkeypatch.setenv("LLM_API_KEY", LLM_API_KEY)
    monkeypatch.setenv("MODEL", MODEL)
    monkeypatch.setenv("AGENT_NAME", AGENT_NAME)
    monkeypatch.setenv("AGENT_DESCRIPTION", AGENT_DESCRIPTION)
    monkeypatch.setenv("AGENT_INSTRUCTIONS", AGENT_INSTRUCTIONS)
    monkeypatch.setenv("LISTEN_PORT", LISTEN_PORT)


def test_config_loads_in_no_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert config.AUTH is None


def test_config_loads_in_api_key_auth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("AGENT_API_KEY", "test-api-key")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert isinstance(config.AUTH, APIKeyAuth)
    assert config.AUTH.api_key == "test-api-key"


def test_config_rejects_empty_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("AGENT_API_KEY", "")

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportCallIssue, reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


def test_config_loads_in_oauth2_mode_with_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("OAUTH2_ISSUER_URL", "https://issuer.example")
    monkeypatch.setenv("OAUTH2_JWKS_URL", "https://issuer.example/jwks")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert isinstance(config.AUTH, OAuth2Auth)
    assert config.AUTH.oauth2_issuer_url == "https://issuer.example"
    assert config.AUTH.oauth2_jwks_url == "https://issuer.example/jwks"


def test_config_loads_in_oauth2_mode_without_jwks_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("OAUTH2_ISSUER_URL", "https://issuer.example")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert isinstance(config.AUTH, OAuth2Auth)
    assert config.AUTH.oauth2_issuer_url == "https://issuer.example"
    assert config.AUTH.oauth2_jwks_url is None


def test_config_rejects_empty_oauth2_issuer_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("OAUTH2_ISSUER_URL", "")

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportCallIssue, reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


@pytest.mark.parametrize(
    ("agent_api_key", "oauth2_issuer_url", "no_auth"),
    [
        ("test-api-key", "https://issuer.example", None),
        ("test-api-key", None, "True"),
        (None, "https://issuer.example", "True"),
        ("test-api-key", "https://issuer.example", "True"),
    ],
)
def test_config_rejects_conflicting_or_no_auth_modes(
    monkeypatch: pytest.MonkeyPatch,
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    no_auth: str | None,
) -> None:
    _set_base_test_env_with(monkeypatch)

    if agent_api_key is not None:
        monkeypatch.setenv("AGENT_API_KEY", agent_api_key)
    if oauth2_issuer_url is not None:
        monkeypatch.setenv("OAUTH2_ISSUER_URL", oauth2_issuer_url)
    if no_auth is not None:
        monkeypatch.setenv("NO_AUTH", no_auth)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


@pytest.mark.parametrize("no_auth", ["TRUE", "TrUe", "1"])
def test_config_accepts_truthy_values_for_no_auth(
    monkeypatch: pytest.MonkeyPatch,
    no_auth: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", no_auth)

    config = Config()  # pyright: ignore[reportCallIssue]

    assert config.AUTH is None


@pytest.mark.parametrize("no_auth_value", ["0", "false", "FaLSe", "", "abc"])
def test_config_requires_other_modes_when_no_auth_is_falsey(
    monkeypatch: pytest.MonkeyPatch,
    no_auth_value: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", no_auth_value)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


@pytest.mark.parametrize("invalid_port", ["abc", "3.14", ""])
def test_config_rejects_invalid_listen_port(
    monkeypatch: pytest.MonkeyPatch,
    invalid_port: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("LISTEN_PORT", invalid_port)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == ("LISTEN_PORT",) for error in exc.value.errors())


@pytest.mark.parametrize(
    "blank_value",
    ["", "    ", "\n  \n"],
)
@pytest.mark.parametrize(
    "env_var",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
    ],
)
def test_config_rejects_blank_value_for_required_field(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    blank_value: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv(env_var, blank_value)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == (env_var,) for error in exc.value.errors())


@pytest.mark.parametrize(
    "missing_env_var",
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
def test_config_raises_when_required_env_var_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    missing_env_var: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.delenv(missing_env_var)

    with pytest.raises(ValidationError) as exc:
        Config()  # pyright: ignore[reportUnusedCallResult, reportCallIssue]

    assert any(error["loc"] == (missing_env_var,) for error in exc.value.errors())


@pytest.mark.parametrize(
    "env_var",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
    ],
)
def test_config_string_field_is_snapshot_at_instantiation(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv(env_var, "original")

    config = Config()  # pyright: ignore[reportCallIssue]
    monkeypatch.setenv(env_var, "new")

    assert getattr(config, env_var) == "original"


def test_config_listen_port_is_snapshot_at_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("LISTEN_PORT", "123")

    config = Config()  # pyright: ignore[reportCallIssue]

    monkeypatch.setenv("LISTEN_PORT", "456")

    assert config.LISTEN_PORT == 123


@pytest.mark.parametrize(
    "env_var",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
    ],
)
def test_config_new_instance_picks_up_updated_string_env_vars(
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv(env_var, "original")

    config = Config()  # pyright: ignore[reportCallIssue]
    monkeypatch.setenv(env_var, "new")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert getattr(config, env_var) == "new"


def test_config_new_instance_picks_up_updated_listen_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("LISTEN_PORT", "123")

    config = Config()  # pyright: ignore[reportCallIssue]

    monkeypatch.setenv("LISTEN_PORT", "456")

    config = Config()  # pyright: ignore[reportCallIssue]

    assert config.LISTEN_PORT == 456


def test_from_env_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "true")

    first = from_env()
    second = from_env()

    assert first is second


def test_from_env_returns_new_instance_after_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")

    first = from_env()
    from_env.cache_clear()
    second = from_env()

    assert first is not second


def test_from_env_exits_when_config_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.delenv("LLM_API_URI")

    with pytest.raises(SystemExit) as exc:
        from_env()  # pyright: ignore[reportUnusedCallResult]

    assert exc.value.code == 1


def test_from_env_mcp_servers_respects_cache_until_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_test_env_with(monkeypatch)
    monkeypatch.setenv("NO_AUTH", "1")
    monkeypatch.setenv("MCP_SERVERS", "mcp://one")

    first = from_env()
    monkeypatch.setenv("MCP_SERVERS", "mcp://two")
    second = from_env()

    assert first is second
    assert second.MCP_SERVERS == ["mcp://one"]

    from_env.cache_clear()
    third = from_env()
    assert third.MCP_SERVERS == ["mcp://two"]
