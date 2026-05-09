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
from src.config.types.auth import OAuthDiscoveredJwksPolicyConfig
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"
STATIC_JWKS_URL = f"{ISSUER_URL}/static-jwks"
DISCOVERED_JWKS_URL = f"{ISSUER_URL}/discovered-jwks"

VALID_JWKS_PAYLOAD: dict[str, JsonValue] = {
    "keys": [
        {
            "kty": "oct",
            "k": "GawgguFyGrWKav7AX4VKUg",
            "kid": "test",
        }
    ]
}

STATIC_JWT_CONFIG = OAuthJwtPolicyConfig(
    jwks=OAuthStaticJwksPolicyConfig(url=Url(STATIC_JWKS_URL)),
    rfc9068=None,
    claims={},
)
DISCOVERED_JWT_CONFIG = OAuthJwtPolicyConfig(
    jwks=OAuthDiscoveredJwksPolicyConfig(),
    rfc9068=None,
    claims={},
)


def _build_middleware(
    *,
    fetch_json: FetchJson,
) -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=OAuthPoliciesConfig(jwt=STATIC_JWT_CONFIG),
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
async def test_fetches_from_static_jwks_url_when_static() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload=VALID_JWKS_PAYLOAD, captured_urls=captured
        ),
    )

    res = await middleware._fetch_jwk_set(jwt_policy_config=STATIC_JWT_CONFIG)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)
    assert captured == [STATIC_JWKS_URL]


@pytest.mark.asyncio
async def test_fetches_from_discovered_jwks_url_when_discovered() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload=VALID_JWKS_PAYLOAD, captured_urls=captured
        ),
    )
    metadata = AuthorizationServerMetadata(
        {"issuer": ISSUER_URL, "jwks_uri": DISCOVERED_JWKS_URL}
    )

    res = await middleware._fetch_jwk_set(  # pyright: ignore[reportPrivateUsage]
        jwt_policy_config=DISCOVERED_JWT_CONFIG,
        metadata=metadata,
    )

    assert isinstance(res, Success)
    assert captured == [DISCOVERED_JWKS_URL]


@pytest.mark.asyncio
async def test_propagates_jwks_uri_discovery_failure() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload=VALID_JWKS_PAYLOAD,
            captured_urls=captured,
        ),
    )
    metadata = AuthorizationServerMetadata(
        {
            "issuer": ISSUER_URL,
            "jwks_uri": "http://insecure.example/jwks",  # https expected, should make discovery fail
        }
    )

    res = await middleware._fetch_jwk_set(  # pyright: ignore[reportPrivateUsage]
        jwt_policy_config=DISCOVERED_JWT_CONFIG,
        metadata=metadata,
    )

    assert isinstance(res, Failure)
    assert res.failure() == (
        "Failed to validate authorization server metadata JWKS URI: "
        '"jwks_uri" MUST use "https" scheme'
    )


@pytest.mark.asyncio
async def test_returns_failure_when_jwks_fetch_raises() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=ValueError("network down")),
    )

    res = await middleware._fetch_jwk_set(jwt_policy_config=STATIC_JWT_CONFIG)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert (
        res.failure() == "Failed to fetch JWKS from authorization server: network down"
    )


@pytest.mark.asyncio
async def test_returns_failure_when_jwks_payload_is_invalid() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"not_keys": []}),
    )

    res = await middleware._fetch_jwk_set(jwt_policy_config=STATIC_JWT_CONFIG)  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert (
        res.failure()
        == "Failed to fetch JWKS from authorization server: Invalid key set format"
    )
