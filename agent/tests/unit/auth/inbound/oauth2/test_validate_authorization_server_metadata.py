from returns.result import Failure, Success
from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware


ISSUER_URL = "https://issuer.example"


def test_validate_metadata_returns_metadata_when_issuer_matches() -> None:
    res = OAuth2BearerAuthMiddleware._validate_authorization_server_metadata(  # pyright: ignore[reportPrivateUsage]
        {"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Success)
    metadata = res.unwrap()

    assert metadata.get("issuer") == ISSUER_URL
    assert metadata.get("jwks_uri") == f"{ISSUER_URL}/jwks"


def test_validate_metadata_accepts_trailing_slash_on_issuer() -> None:
    res = OAuth2BearerAuthMiddleware._validate_authorization_server_metadata(  # pyright: ignore[reportPrivateUsage]
        {"issuer": f"{ISSUER_URL}/", "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Success)
    metadata = res.unwrap()

    assert metadata.get("issuer") == f"{ISSUER_URL}/"


def test_validate_metadata_rejects_issuer_mismatch() -> None:
    res = OAuth2BearerAuthMiddleware._validate_authorization_server_metadata(  # pyright: ignore[reportPrivateUsage]
        {"issuer": "https://other.example", "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Failure)
    assert (
        res.failure()
        == "Failed to validate authorization server metadata: Issuer mismatch in OAuth2 authorization server metadata"
    )


def test_validate_metadata_rejects_missing_issuer() -> None:
    res = OAuth2BearerAuthMiddleware._validate_authorization_server_metadata(  # pyright: ignore[reportPrivateUsage]
        {"jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )
    assert isinstance(res, Failure)
    assert (
        res.failure()
        == 'Failed to validate authorization server metadata: "issuer" is required'
    )
