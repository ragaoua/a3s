import asyncio
import base64
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import parse_qs

import httpx
from pydantic import SecretStr
import pytest
from pydantic_core import Url

import src.mcp.internal.oauth_client_credentials as oauth_client_credentials_module
from src.config.types import McpServerOAuthClientCredentialsAuthConfig
from src.mcp.internal.oauth_client_credentials import OAuthClientCredentialsAuth
from src.mcp.internal.types import AccessTokenInfo


@pytest.fixture(autouse=True)
def clear_access_token_cache():
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE.clear()
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE_LOCKS.clear()
    yield
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE.clear()
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE_LOCKS.clear()


def _build_auth(
    auth_method: Literal[
        "client_secret_basic", "client_secret_post"
    ] = "client_secret_basic",
) -> OAuthClientCredentialsAuth:
    return OAuthClientCredentialsAuth(
        server_url=Url("https://mcp.example"),
        server_auth_config=McpServerOAuthClientCredentialsAuthConfig(
            mode="oauth_client_credentials",
            token_endpoint=Url("https://issuer.example/oauth/token"),
            client_id="client-id",
            client_secret=SecretStr("client-secret"),
            auth_method=auth_method,
        ),
    )


def test_build_factory_uses_default_auth_when_none_is_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_create_mcp_http_client(*, headers=None, timeout=None, auth=None):
        captured["headers"] = headers
        captured["timeout"] = timeout
        captured["auth"] = auth
        return sentinel

    monkeypatch.setattr(
        oauth_client_credentials_module,
        "create_mcp_http_client",
        fake_create_mcp_http_client,
    )

    factory = OAuthClientCredentialsAuth.build_factory(
        auth._server_url,
        auth._server_auth_config,
    )
    timeout = httpx.Timeout(5.0)

    result = factory(headers={"X-Test": "1"}, timeout=timeout)

    assert result is sentinel
    assert captured["headers"] == {"X-Test": "1"}
    assert captured["timeout"] is timeout
    assert isinstance(captured["auth"], OAuthClientCredentialsAuth)


def test_is_unauthorized_bearer_requires_401_and_bearer_header() -> None:
    auth = _build_auth()

    assert auth.isUnauthorizedBearer(
        httpx.Response(
            401,
            headers=[
                ("WWW-Authenticate", "Digest realm=test"),
                ("WWW-Authenticate", "Bearer realm=test"),
            ],
        )
    )
    assert not auth.isUnauthorizedBearer(
        httpx.Response(200, headers={"WWW-Authenticate": "Bearer realm=test"})
    )


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_requires_lock() -> None:
    auth = _build_auth()

    with pytest.raises(RuntimeError, match="cache lock must be acquired first"):
        await auth.fetch_access_token_from_auth_server()


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_uses_basic_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth("client_secret_basic")
    expected_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    captured_request: httpx.Request | None = None

    async def fake_fetch_json(request, *, error_message, error_cls=ValueError):
        nonlocal captured_request
        captured_request = request
        assert "Failed to fetch OAuth2 access token" in error_message
        return {"access_token": "token-123", "expires_in": 60}

    monkeypatch.setattr(oauth_client_credentials_module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(
        oauth_client_credentials_module,
        "get_access_token_expiry_date",
        lambda token_response, access_token: expected_expiry,
    )

    lock = auth._ACCESS_TOKEN_CACHE_LOCKS.setdefault(auth._cache_key, asyncio.Lock())
    async with lock:
        token_info = await auth.fetch_access_token_from_auth_server()

    assert captured_request is not None
    assert captured_request.method == "POST"
    assert str(captured_request.url) == "https://issuer.example/oauth/token"
    assert captured_request.headers["Accept"] == "application/json"
    assert (
        captured_request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    )
    assert captured_request.headers["Authorization"] == "Basic " + base64.b64encode(
        b"client-id:client-secret"
    ).decode("ascii")
    assert parse_qs(captured_request.content.decode("utf-8")) == {
        "grant_type": ["client_credentials"]
    }
    assert token_info == AccessTokenInfo("token-123", expected_expiry)
    assert auth._ACCESS_TOKEN_CACHE[auth._cache_key] == token_info


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_uses_client_secret_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth("client_secret_post")
    captured_request: httpx.Request | None = None

    async def fake_fetch_json(request, *, error_message, error_cls=ValueError):
        nonlocal captured_request
        captured_request = request
        return {"access_token": "token-123"}

    monkeypatch.setattr(oauth_client_credentials_module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(
        oauth_client_credentials_module,
        "get_access_token_expiry_date",
        lambda token_response, access_token: None,
    )

    lock = auth._ACCESS_TOKEN_CACHE_LOCKS.setdefault(auth._cache_key, asyncio.Lock())
    async with lock:
        token_info = await auth.fetch_access_token_from_auth_server()

    assert captured_request is not None
    assert "Authorization" not in captured_request.headers
    assert parse_qs(captured_request.content.decode("utf-8")) == {
        "grant_type": ["client_credentials"],
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
    }
    assert token_info == AccessTokenInfo("token-123", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("access_token", [None, "", 123])
async def test_fetch_access_token_from_auth_server_rejects_invalid_access_token(
    access_token: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()

    async def fake_fetch_json(request, *, error_message, error_cls=ValueError):
        return {"access_token": access_token}

    monkeypatch.setattr(oauth_client_credentials_module, "fetch_json", fake_fetch_json)

    lock = auth._ACCESS_TOKEN_CACHE_LOCKS.setdefault(auth._cache_key, asyncio.Lock())
    async with lock:
        with pytest.raises(
            ValueError,
            match="missing a valid 'access_token'",
        ):
            await auth.fetch_access_token_from_auth_server()


@pytest.mark.asyncio
async def test_async_auth_flow_retries_once_when_cached_token_gets_bearer_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()
    cached_token = AccessTokenInfo(
        "cached-token",
        datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    refreshed_token = AccessTokenInfo(
        "fresh-token",
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    auth._ACCESS_TOKEN_CACHE[auth._cache_key] = cached_token
    fetch_calls = 0
    authorization_headers: list[str] = []
    responses = [
        httpx.Response(401, headers={"WWW-Authenticate": "Bearer realm=test"}),
        httpx.Response(200),
    ]

    async def fake_fetch(self: OAuthClientCredentialsAuth) -> AccessTokenInfo:
        nonlocal fetch_calls
        fetch_calls += 1
        self._ACCESS_TOKEN_CACHE[self._cache_key] = refreshed_token
        return refreshed_token

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return responses.pop(0)

    monkeypatch.setattr(
        OAuthClientCredentialsAuth,
        "fetch_access_token_from_auth_server",
        fake_fetch,
    )

    async with httpx.AsyncClient(
        auth=auth,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == ["Bearer cached-token", "Bearer fresh-token"]
    assert fetch_calls == 1
    assert auth._ACCESS_TOKEN_CACHE[auth._cache_key] == refreshed_token


@pytest.mark.asyncio
async def test_async_auth_flow_does_not_retry_after_initial_token_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()
    fresh_token = AccessTokenInfo(
        "fresh-token",
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    fetch_calls = 0
    authorization_headers: list[str] = []

    async def fake_fetch(self: OAuthClientCredentialsAuth) -> AccessTokenInfo:
        nonlocal fetch_calls
        fetch_calls += 1
        self._ACCESS_TOKEN_CACHE[self._cache_key] = fresh_token
        return fresh_token

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(401, headers={"WWW-Authenticate": "Bearer realm=test"})

    monkeypatch.setattr(
        OAuthClientCredentialsAuth,
        "fetch_access_token_from_auth_server",
        fake_fetch,
    )

    async with httpx.AsyncClient(
        auth=auth,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 401
    assert authorization_headers == ["Bearer fresh-token"]
    assert fetch_calls == 1
    assert auth._cache_key not in auth._ACCESS_TOKEN_CACHE


@pytest.mark.asyncio
async def test_async_auth_flow_uses_still_valid_cached_token_when_refresh_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()
    cached_token = AccessTokenInfo(
        "cached-token",
        datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    auth._ACCESS_TOKEN_CACHE[auth._cache_key] = cached_token
    authorization_headers: list[str] = []

    async def fake_fetch(self: OAuthClientCredentialsAuth) -> AccessTokenInfo:
        raise RuntimeError("refresh failed")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(401, headers={"WWW-Authenticate": "Bearer realm=test"})

    monkeypatch.setattr(
        OAuthClientCredentialsAuth,
        "fetch_access_token_from_auth_server",
        fake_fetch,
    )

    async with httpx.AsyncClient(
        auth=auth,
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 401
    assert authorization_headers == ["Bearer cached-token"]
    assert auth._cache_key not in auth._ACCESS_TOKEN_CACHE


@pytest.mark.asyncio
async def test_async_auth_flow_raises_when_expired_cached_token_cannot_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _build_auth()
    auth._ACCESS_TOKEN_CACHE[auth._cache_key] = AccessTokenInfo(
        "expired-token",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    handler_called = False

    async def fake_fetch(self: OAuthClientCredentialsAuth) -> AccessTokenInfo:
        raise RuntimeError("refresh failed")

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal handler_called
        handler_called = True
        return httpx.Response(200)

    monkeypatch.setattr(
        OAuthClientCredentialsAuth,
        "fetch_access_token_from_auth_server",
        fake_fetch,
    )

    async with httpx.AsyncClient(
        auth=auth,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(RuntimeError, match="refresh failed"):
            await client.get("https://api.example/resource")

    assert not handler_called
