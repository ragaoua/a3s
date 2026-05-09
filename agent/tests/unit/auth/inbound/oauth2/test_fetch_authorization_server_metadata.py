import httpx
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
WELL_KNOWN_URL = f"{ISSUER_URL}/.well-known/oauth-authorization-server"


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
async def test_returns_metadata_on_successful_fetch_and_validation() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload={"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
        ),
    )

    res = await middleware._fetch_authorization_server_metadata()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)
    metadata = res.unwrap()
    assert metadata.get("issuer") == ISSUER_URL
    assert metadata.get("jwks_uri") == f"{ISSUER_URL}/jwks"


@pytest.mark.asyncio
async def test_fetches_from_rfc8414_well_known_url() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload={"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
            captured_urls=captured,
        ),
    )

    _ = await middleware._fetch_authorization_server_metadata()  # pyright: ignore[reportPrivateUsage]

    assert captured == [WELL_KNOWN_URL]


@pytest.mark.asyncio
async def test_strips_trailing_slash_on_issuer_url_when_building_well_known_url() -> (
    None
):
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        issuer_url=f"{ISSUER_URL}/",
        fetch_json=_build_fetch_json(
            payload={"issuer": ISSUER_URL, "jwks_uri": f"{ISSUER_URL}/jwks"},
            captured_urls=captured,
        ),
    )

    res = await middleware._fetch_authorization_server_metadata()  # pyright: ignore[reportPrivateUsage]

    assert captured == [WELL_KNOWN_URL]
    assert isinstance(res, Success)


@pytest.mark.asyncio
async def test_returns_failure_when_fetch_json_raises() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=ValueError("network down")),
    )

    res = await middleware._fetch_authorization_server_metadata()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert (
        res.failure() == "Failed to fetch authorization server metadata: network down"
    )


@pytest.mark.asyncio
async def test_returns_failure_when_validation_fails() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(
            payload={
                "issuer": "https://other.example",  # Wrong issuer, validation should fail
                "jwks_uri": f"{ISSUER_URL}/jwks",
            },
        ),
    )

    res = await middleware._fetch_authorization_server_metadata()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
