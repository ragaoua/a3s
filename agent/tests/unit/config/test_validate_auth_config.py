import pytest

from src.config import APIKeyAuth, OAuth2Auth, validate_auth_config


def test_validate_auth_config_accepts_no_auth_mode() -> None:
    assert (
        validate_auth_config(
            agent_api_key=None,
            oauth2_issuer_url=None,
            oauth2_jwks_url=None,
            oauth2_audience=None,
            no_auth=True,
        )
        is None
    )


def test_validate_auth_config_accepts_api_key_mode() -> None:
    auth = validate_auth_config(
        agent_api_key="test-api-key",
        oauth2_issuer_url=None,
        oauth2_jwks_url=None,
        oauth2_audience=None,
        no_auth=False,
    )

    assert isinstance(auth, APIKeyAuth)
    assert auth.api_key == "test-api-key"


@pytest.mark.parametrize(
    ("oauth2_jwks_url"),
    [None, "https://issuer.example/jwks"],
)
@pytest.mark.parametrize(
    "oauth2_audience",
    [None, "api://agent"],
)
def test_validate_auth_config_accepts_oauth2_mode(
    oauth2_jwks_url: str | None,
    oauth2_audience: str | None,
) -> None:
    auth = validate_auth_config(
        agent_api_key=None,
        oauth2_issuer_url="https://issuer.example",
        oauth2_jwks_url=oauth2_jwks_url,
        oauth2_audience=oauth2_audience,
        no_auth=False,
    )

    assert isinstance(auth, OAuth2Auth)
    assert auth.oauth2_issuer_url == "https://issuer.example"
    assert auth.oauth2_jwks_url == oauth2_jwks_url
    assert auth.oauth2_audience == oauth2_audience


@pytest.mark.parametrize(
    (
        "agent_api_key",
        "oauth2_issuer_url",
        "oauth2_jwks_url",
        "oauth2_audience",
        "no_auth",
    ),
    [
        ("test-api-key", "https://issuer.example", None, None, True),
        ("test-api-key", "https://issuer.example", None, "api://agent", False),
        ("test-api-key", None, None, None, True),
        (None, "https://issuer.example", None, None, True),
        (None, "", None, None, False),
        ("", None, None, None, False),
        (None, None, None, None, False),
    ],
)
def test_validate_auth_config_rejects_multiple_auth_modes_or_none(
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    oauth2_jwks_url: str | None,
    oauth2_audience: str | None,
    no_auth: bool,
) -> None:
    with pytest.raises(ValueError):
        validate_auth_config(  # pyright: ignore[reportUnusedCallResult]
            agent_api_key=agent_api_key,
            oauth2_issuer_url=oauth2_issuer_url,
            oauth2_jwks_url=oauth2_jwks_url,
            oauth2_audience=oauth2_audience,
            no_auth=no_auth,
        )
