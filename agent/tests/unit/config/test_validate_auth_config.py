import pytest

from src.config import APIKeyAuth, OAuth2Auth, validate_auth_config


def test_validate_auth_config_accepts_no_auth_mode() -> None:
    assert (
        validate_auth_config(
            agent_api_key=None,
            oauth2_issuer_url=None,
            oauth2_jwks_url=None,
            no_auth=True,
        )
        is None
    )


def test_validate_auth_config_accepts_api_key_mode() -> None:
    auth = validate_auth_config(
        agent_api_key="test-api-key",
        oauth2_issuer_url=None,
        oauth2_jwks_url=None,
        no_auth=False,
    )

    assert isinstance(auth, APIKeyAuth)
    assert auth.api_key == "test-api-key"


def test_validate_auth_config_accepts_oauth2_mode_with_jwks_url() -> None:
    auth = validate_auth_config(
        agent_api_key=None,
        oauth2_issuer_url="https://issuer.example",
        oauth2_jwks_url="https://issuer.example/jwks",
        no_auth=False,
    )

    assert isinstance(auth, OAuth2Auth)
    assert auth.oauth2_issuer_url == "https://issuer.example"
    assert auth.oauth2_jwks_url == "https://issuer.example/jwks"


def test_validate_auth_config_accepts_oauth2_mode_without_jwks_url() -> None:
    auth = validate_auth_config(
        agent_api_key=None,
        oauth2_issuer_url="https://issuer.example",
        oauth2_jwks_url=None,
        no_auth=False,
    )

    assert isinstance(auth, OAuth2Auth)
    assert auth.oauth2_issuer_url == "https://issuer.example"
    assert auth.oauth2_jwks_url is None


@pytest.mark.parametrize(
    ("agent_api_key", "oauth2_issuer_url", "oauth2_jwks_url", "no_auth"),
    [
        ("test-api-key", "https://issuer.example", None, True),
        ("test-api-key", "https://issuer.example", None, False),
        ("test-api-key", None, None, True),
        (None, "https://issuer.example", None, True),
        (None, "", None, False),
        ("", None, None, False),
        (None, None, None, False),
    ],
)
def test_validate_auth_config_rejects_multiple_auth_modes_or_none(
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    oauth2_jwks_url: str | None,
    no_auth: bool,
) -> None:
    with pytest.raises(ValueError):
        validate_auth_config(  # pyright: ignore[reportUnusedCallResult]
            agent_api_key=agent_api_key,
            oauth2_issuer_url=oauth2_issuer_url,
            oauth2_jwks_url=oauth2_jwks_url,
            no_auth=no_auth,
        )
