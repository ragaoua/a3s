import httpx
import pytest
from pydantic import JsonValue
from returns.result import Failure, Success

from src.auth.oauth_metadata import (
    fetch_authorization_server_metadata,
    validate_authorization_server_metadata,
)
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"
WELL_KNOWN_URL = f"{ISSUER_URL}/.well-known/oauth-authorization-server"


def _build_fetch_json(
    *,
    payload: dict[str, JsonValue] | None = None,
    raises: Exception | None = None,
    captured_urls: list[str | httpx.Request] | None = None,
) -> FetchJson:
    async def _fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        if captured_urls is not None:
            captured_urls.append(url)
        if raises is not None:
            raise raises
        assert payload is not None
        return payload

    return _fetch_json


# --- fetch_authorization_server_metadata ------------------------------------


@pytest.mark.asyncio
async def test_fetches_from_rfc8414_well_known_url() -> None:
    captured: list[str | httpx.Request] = []
    res = await fetch_authorization_server_metadata(
        ISSUER_URL,
        fetch_json=_build_fetch_json(
            payload={"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
            captured_urls=captured,
        ),
    )

    assert captured == [WELL_KNOWN_URL]
    assert isinstance(res, Success)
    metadata = res.unwrap()
    assert metadata.get("issuer") == ISSUER_URL
    assert metadata.get("jwks_uri") == f"{ISSUER_URL}/jwks"


@pytest.mark.asyncio
async def test_returns_failure_when_fetch_json_raises() -> None:
    res = await fetch_authorization_server_metadata(
        ISSUER_URL,
        fetch_json=_build_fetch_json(raises=ValueError("network down")),
    )

    assert isinstance(res, Failure)
    assert (
        res.failure() == "Failed to fetch authorization server metadata: network down"
    )


@pytest.mark.asyncio
async def test_returns_failure_when_validation_fails() -> None:
    res = await fetch_authorization_server_metadata(
        ISSUER_URL,
        fetch_json=_build_fetch_json(
            payload={"issuer": "https://other.example"},
        ),
    )

    assert isinstance(res, Failure)


# --- validate_authorization_server_metadata ---------------------------------


def test_validate_returns_metadata_when_issuer_matches() -> None:
    res = validate_authorization_server_metadata(
        {"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Success)
    metadata = res.unwrap()
    assert metadata.get("issuer") == ISSUER_URL
    assert metadata.get("jwks_uri") == f"{ISSUER_URL}/jwks"


def test_validate_accepts_trailing_slash_on_issuer() -> None:
    res = validate_authorization_server_metadata(
        {"issuer": f"{ISSUER_URL}/", "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Success)
    assert res.unwrap().get("issuer") == f"{ISSUER_URL}/"


def test_validate_rejects_issuer_mismatch() -> None:
    res = validate_authorization_server_metadata(
        {"issuer": "https://other.example", "jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Failure)
    assert (
        res.failure()
        == "Failed to validate authorization server metadata: Issuer mismatch in OAuth2 authorization server metadata"
    )


def test_validate_rejects_missing_issuer() -> None:
    res = validate_authorization_server_metadata(
        {"jwks_uri": f"{ISSUER_URL}/jwks"},
        expected_issuer=ISSUER_URL,
    )

    assert isinstance(res, Failure)
    assert (
        res.failure()
        == 'Failed to validate authorization server metadata: "issuer" is required'
    )
