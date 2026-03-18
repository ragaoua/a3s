import pytest
from pydantic import ValidationError

from src.config import (
    APIKeyAuth,
    OAuth2Auth,
)
from tests.utils import get_base_test_config_ignoring_env_file_with


def test_config_loads_in_no_auth_mode() -> None:
    config = get_base_test_config_ignoring_env_file_with(NO_AUTH=True)

    assert config.AUTH is None


def test_config_loads_in_api_key_auth_mode() -> None:
    config = get_base_test_config_ignoring_env_file_with(AGENT_API_KEY="test-api-key")

    assert isinstance(config.AUTH, APIKeyAuth)
    assert config.AUTH.api_key == "test-api-key"


def test_config_rejects_empty_api_key() -> None:
    with pytest.raises(ValidationError) as exc:
        get_base_test_config_ignoring_env_file_with(
            AGENT_API_KEY=""
        )  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


def test_config_loads_in_oauth2_mode_with_jwks_url() -> None:
    config = get_base_test_config_ignoring_env_file_with(
        OAUTH2_ISSUER_URL="https://issuer.example",
        OAUTH2_JWKS_URL="https://issuer.example/jwks",
    )

    assert isinstance(config.AUTH, OAuth2Auth)
    assert config.AUTH.oauth2_issuer_url == "https://issuer.example"
    assert config.AUTH.oauth2_jwks_url == "https://issuer.example/jwks"


def test_config_loads_in_oauth2_mode_without_jwks_url() -> None:
    config = get_base_test_config_ignoring_env_file_with(
        OAUTH2_ISSUER_URL="https://issuer.example"
    )

    assert isinstance(config.AUTH, OAuth2Auth)
    assert config.AUTH.oauth2_issuer_url == "https://issuer.example"
    assert config.AUTH.oauth2_jwks_url is None


def test_config_rejects_empty_oauth2_issuer_url() -> None:
    with pytest.raises(ValidationError) as exc:
        get_base_test_config_ignoring_env_file_with(
            OAUTH2_ISSUER_URL=""
        )  # pyright: ignore[reportUnusedCallResult]

    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


@pytest.mark.parametrize(
    ("agent_api_key", "oauth2_issuer_url", "no_auth"),
    [
        ("test-api-key", "https://issuer.example", False),
        ("test-api-key", None, True),
        (None, "https://issuer.example", True),
        ("test-api-key", "https://issuer.example", True),
        (None, None, False),
    ],
)
def test_config_rejects_conflicting_or_no_auth_modes(
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    no_auth: bool,
) -> None:
    with pytest.raises(ValidationError) as exc:
        get_base_test_config_ignoring_env_file_with(  # pyright: ignore[reportUnusedCallResult]
            AGENT_API_KEY=agent_api_key,
            OAUTH2_ISSUER_URL=oauth2_issuer_url,
            NO_AUTH=no_auth,
        )
    assert any(error["loc"] == ("Auth",) for error in exc.value.errors())


@pytest.mark.parametrize(
    "field",
    [
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
    ],
)
def test_config_rejects_empty_required_string_fields(field: str) -> None:
    config = get_base_test_config_ignoring_env_file_with(NO_AUTH=True)
    setattr(config, field, "")

    with pytest.raises(ValidationError) as exc:
        get_base_test_config_ignoring_env_file_with(  # pyright: ignore[reportUnusedCallResult]
            **(config.__dict__)  # pyright: ignore[reportAny]
        )

    assert any(error["loc"] == (field,) for error in exc.value.errors())
