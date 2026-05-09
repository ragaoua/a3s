import base64
import json
from typing import Literal

import httpx
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata
from pydantic import JsonValue, SecretStr
import pytest
from pydantic_core import Url
from returns.result import Failure, Success
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
)
from src.config.types.auth import OAuthDiscoveredIntrospectionPolicyConfig
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"
STATIC_INTROSPECTION_URL = f"{ISSUER_URL}/static-introspect"
DISCOVERED_INTROSPECTION_URL = f"{ISSUER_URL}/discovered-introspect"

CLIENT_ID = "client"
CLIENT_SECRET = SecretStr("secret")

STATIC_INTROSPECTION_CONFIG = OAuthStaticIntrospectionPolicyConfig(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    endpoint=Url(STATIC_INTROSPECTION_URL),
)
DISCOVERED_INTROSPECTION_CONFIG = OAuthDiscoveredIntrospectionPolicyConfig(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
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
        config=OAuthPoliciesConfig(introspection=STATIC_INTROSPECTION_CONFIG),
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
async def test_returns_success_when_token_is_active_using_static_endpoint() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"active": True}, captured_urls=captured),
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token", introspection_config=STATIC_INTROSPECTION_CONFIG
    )

    assert isinstance(res, Success)
    captured_urls = [
        str(c.url) if isinstance(c, httpx.Request) else c for c in captured
    ]
    assert captured_urls == [STATIC_INTROSPECTION_URL]


@pytest.mark.asyncio
async def test_returns_success_when_token_is_active_using_discovered_endpoint() -> None:
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"active": True}, captured_urls=captured),
    )
    metadata = AuthorizationServerMetadata(
        {
            "issuer": ISSUER_URL,
            "introspection_endpoint": DISCOVERED_INTROSPECTION_URL,
        }
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token",
        introspection_config=DISCOVERED_INTROSPECTION_CONFIG,
        metadata=metadata,
    )

    assert isinstance(res, Success)
    captured_urls = [
        str(c.url) if isinstance(c, httpx.Request) else c for c in captured
    ]
    assert captured_urls == [DISCOVERED_INTROSPECTION_URL]


@pytest.mark.asyncio
async def test_fails_with_503_when_introspection_endpoint_discovery_fails() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"active": True}),
    )

    metadata = AuthorizationServerMetadata(
        {
            "issuer": ISSUER_URL,
            "introspection_endpoint": "http://insecure.example/token_info",  # https expected, should make discovery fail
        }
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token",
        introspection_config=DISCOVERED_INTROSPECTION_CONFIG,
        metadata=metadata,
    )

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "detail": 'Failed to validate authorization server metadata introspection endpoint: "introspection_endpoint" MUST use "https" scheme'
    }


@pytest.mark.asyncio
async def test_fails_with_503_when_introspection_fetch_raises() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(raises=ValueError("network down")),
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token", introspection_config=STATIC_INTROSPECTION_CONFIG
    )

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "detail": (
            f"Failed to introspect token via '{STATIC_INTROSPECTION_URL}': network down"
        )
    }


@pytest.mark.asyncio
async def test_returns_unauthorized_when_token_is_inactive() -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"active": False}),
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token", introspection_config=STATIC_INTROSPECTION_CONFIG
    )

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_token", '
        'error_description="The access token provided is expired, revoked, '
        'malformed, or invalid for other reasons."'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"active": "true"},
        {"active": 1},
        {"active": None},
    ],
    ids=["missing", "string", "int", "null"],
)
async def test_returns_503_when_active_flag_is_missing_or_not_boolean(
    payload: dict[str, JsonValue],
) -> None:
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload=payload),
    )

    res = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token", introspection_config=STATIC_INTROSPECTION_CONFIG
    )

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "detail": "OAuth2 token introspection response is missing a valid 'active' flag"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_method",
    ["client_secret_basic", "client_secret_post"],
)
async def test_uses_introspection_config_credentials_in_request(
    auth_method: Literal["client_secret_basic", "client_secret_post"],
) -> None:
    introspection_config = OAuthStaticIntrospectionPolicyConfig(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        endpoint=Url(STATIC_INTROSPECTION_URL),
        auth_method=auth_method,
    )
    captured: list[str | httpx.Request] = []
    middleware = _build_middleware(
        fetch_json=_build_fetch_json(payload={"active": True}, captured_urls=captured),
    )

    _ = await middleware._introspect_access_token(  # pyright: ignore[reportPrivateUsage]
        "token", introspection_config=introspection_config
    )

    request = captured[0]
    assert isinstance(request, httpx.Request)
    if auth_method == "client_secret_basic":
        assert (
            request.headers["Authorization"]
            == f"Basic {base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET.get_secret_value()}'.encode()).decode()}"
        )
    else:
        body = request.content.decode("utf-8")
        assert f"client_id={CLIENT_ID}" in body
        assert f"client_secret={CLIENT_SECRET.get_secret_value()}" in body
