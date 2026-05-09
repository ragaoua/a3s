import httpx
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata
from pydantic import JsonValue
import pytest
from pydantic_core import Url
from returns.result import Failure, Success
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"
JWKS_URL = f"{ISSUER_URL}/jwks"


def _build_middleware(
    *,
    issuer_url: str = ISSUER_URL,
    fetch_json: FetchJson,
) -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=issuer_url,
        realm="test-realm",
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
                rfc9068=None,
                claims={},
            )
        ),
        fetch_json=fetch_json,
    )


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


@pytest.mark.asyncio
async def test_returns_jwks_uri_when_metadata_passed_in() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=AssertionError("should not be called")),
    )
    metadata = AuthorizationServerMetadata(
        {"issuer": ISSUER_URL, "jwks_uri": JWKS_URL}
    )

    res = await middleware._discover_jwks_uri(metadata)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)
    assert res.unwrap() == JWKS_URL


@pytest.mark.asyncio
async def test_fetches_metadata_when_no_metadata_passed_in() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload={"issuer": ISSUER_URL, "jwks_uri": JWKS_URL},
            captured_urls=captured,
        ),
    )

    res = await middleware._discover_jwks_uri()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)
    assert res.unwrap() == JWKS_URL
    assert captured == [f"{ISSUER_URL}/.well-known/oauth-authorization-server"]


@pytest.mark.asyncio
async def test_returns_failure_when_fetching_metadata_fails() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=ValueError("network down")),
    )

    res = await middleware._discover_jwks_uri()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert (
        res.failure() == "Failed to fetch authorization server metadata: network down"
    )


@pytest.mark.asyncio
async def test_returns_failure_when_jwks_uri_uses_insecure_scheme() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=AssertionError("should not be called")),
    )
    metadata = AuthorizationServerMetadata(
        {"issuer": ISSUER_URL, "jwks_uri": "http://insecure.example/jwks"}
    )

    res = await middleware._discover_jwks_uri(metadata)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert res.failure() == (
        "Failed to validate authorization server metadata JWKS URI: "
        '"jwks_uri" MUST use "https" scheme'
    )


@pytest.mark.asyncio
async def test_returns_failure_when_jwks_uri_is_missing() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=AssertionError("should not be called")),
    )
    metadata = AuthorizationServerMetadata({"issuer": ISSUER_URL})

    res = await middleware._discover_jwks_uri(metadata)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert (
        res.failure()
        == "OAuth2 authorization server metadata does not contain a valid jwks_uri"
    )
