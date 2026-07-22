from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import JsonValue, SecretStr
from pydantic_core import Url

from src.auth.context import bind_current_authorization_header
from src.auth.outbound.oauth_token_exchange import OAuthTokenExchangeAuth
from src.auth.outbound.types import AccessTokenInfo, TokenExchangeCacheKey
from src.config.types import (
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthStaticTokenExchangeAuthConfig,
)
from src.utils import FetchJson, fetch_json as _default_fetch_json

_TOKEN_ENDPOINT = Url("https://issuer.example/oauth/token")
_ISSUER_URL = "https://issuer.example"


@pytest.fixture(autouse=True)
def clear_caches() -> Generator[None, None, None]:
    OAuthTokenExchangeAuth._access_token_cache.clear()  # pyright: ignore[reportPrivateUsage]
    OAuthTokenExchangeAuth._access_token_cache_locks.clear()  # pyright: ignore[reportPrivateUsage]
    yield


def _build_static_auth(
    *,
    fetch_json: FetchJson = _default_fetch_json,
    auth_method: Literal[
        "client_secret_basic", "client_secret_post"
    ] = "client_secret_basic",
) -> OAuthTokenExchangeAuth:
    return OAuthTokenExchangeAuth(
        server_url=Url("https://mcp.example"),
        server_auth_config=OAuthStaticTokenExchangeAuthConfig(
            mode="oauth_token_exchange",
            token_endpoint=_TOKEN_ENDPOINT,
            client_id="client-id",
            client_secret=SecretStr("client-secret"),
            auth_method=auth_method,
        ),
        fetch_json=fetch_json,
    )


def _build_discovered_auth(
    *,
    fetch_json: FetchJson = _default_fetch_json,
) -> OAuthTokenExchangeAuth:
    return OAuthTokenExchangeAuth(
        server_url=Url("https://mcp.example"),
        server_auth_config=OAuthDiscoveredTokenExchangeAuthConfig(
            mode="oauth_token_exchange",
            client_id="client-id",
            client_secret=SecretStr("client-secret"),
            issuer_url=Url(_ISSUER_URL),
        ),
        fetch_json=fetch_json,
    )


# --- subject token extraction ------------------------------------------------


def test_get_subject_token_returns_bearer_token() -> None:
    with bind_current_authorization_header("Bearer subject-abc"):
        assert OAuthTokenExchangeAuth._get_subject_token() == "subject-abc"  # pyright: ignore[reportPrivateUsage]


def test_get_subject_token_raises_when_no_inbound_header() -> None:
    with pytest.raises(ValueError, match="no inbound Authorization header"):
        _ = OAuthTokenExchangeAuth._get_subject_token()  # pyright: ignore[reportPrivateUsage]


def test_get_subject_token_raises_for_non_bearer_scheme() -> None:
    with bind_current_authorization_header("Basic Zm9vOmJhcg=="):
        with pytest.raises(ValueError, match="must be a Bearer token"):
            _ = OAuthTokenExchangeAuth._get_subject_token()  # pyright: ignore[reportPrivateUsage]


# --- token endpoint resolution ----------------------------------------------


@pytest.mark.asyncio
async def test_resolve_token_endpoint_static_returns_configured_endpoint() -> None:
    auth = _build_static_auth()
    assert await auth._resolve_token_endpoint() == _TOKEN_ENDPOINT  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_resolve_token_endpoint_discovered_fetches_metadata() -> None:
    fetched_urls: list[str] = []

    async def fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        fetched_urls.append(str(url))
        return {
            "issuer": _ISSUER_URL,
            "token_endpoint": "https://issuer.example/oauth/token",
        }

    auth = _build_discovered_auth(fetch_json=fetch_json)

    endpoint = await auth._resolve_token_endpoint()  # pyright: ignore[reportPrivateUsage]

    assert endpoint == _TOKEN_ENDPOINT
    assert fetched_urls == [
        "https://issuer.example/.well-known/oauth-authorization-server"
    ]


@pytest.mark.asyncio
async def test_resolve_token_endpoint_discovered_raises_on_issuer_mismatch() -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {
            "issuer": "https://evil.example",
            "token_endpoint": "https://evil.example/oauth/token",
        }

    auth = _build_discovered_auth(fetch_json=fetch_json)

    with pytest.raises(ValueError, match="Issuer mismatch"):
        _ = await auth._resolve_token_endpoint()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_resolve_token_endpoint_discovered_raises_when_endpoint_missing() -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"issuer": _ISSUER_URL}

    auth = _build_discovered_auth(fetch_json=fetch_json)

    with pytest.raises(ValueError, match="does not contain a valid token_endpoint"):
        _ = await auth._resolve_token_endpoint()  # pyright: ignore[reportPrivateUsage]


# --- token exchange request building ----------------------------------------


def _cache_key(subject_token: str) -> TokenExchangeCacheKey:
    return TokenExchangeCacheKey(
        _TOKEN_ENDPOINT,
        "client-id",
        OAuthTokenExchangeAuth._hash_subject_token(subject_token),  # pyright: ignore[reportPrivateUsage]
    )


@pytest.mark.asyncio
async def test_exchange_token_builds_rfc8693_request_and_caches() -> None:
    captured: dict[str, list[str]] = {}

    async def fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        assert isinstance(url, httpx.Request)
        captured.update(parse_qs(url.content.decode("utf-8")))
        return {"access_token": "exchanged-token", "expires_in": 300}

    auth = _build_static_auth(fetch_json=fetch_json)

    with bind_current_authorization_header("Bearer subject-abc"):
        prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
        async with auth._access_token_cache_locks[prepared_grant.cache_key]:  # pyright: ignore[reportPrivateUsage]
            token_info = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]

    assert prepared_grant.cache_key == _cache_key("subject-abc")
    assert captured["grant_type"] == ["urn:ietf:params:oauth:grant-type:token-exchange"]
    assert captured["subject_token"] == ["subject-abc"]
    assert captured["subject_token_type"] == [
        "urn:ietf:params:oauth:token-type:access_token"
    ]
    assert token_info.access_token == "exchanged-token"
    assert auth._access_token_cache[prepared_grant.cache_key] is token_info  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_exchange_token_raises_when_lock_not_acquired() -> None:
    auth = _build_static_auth()

    with bind_current_authorization_header("Bearer subject-abc"):
        prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
        # The lock guard fires before the grant runs, so calling without the
        # lock held raises.
        with pytest.raises(RuntimeError, match="cache lock must be acquired first"):
            _ = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]


# --- subject-scoped caching + eviction --------------------------------------


@pytest.mark.asyncio
async def test_exchange_token_scopes_cache_per_subject() -> None:
    async def fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        assert isinstance(url, httpx.Request)
        subject = parse_qs(url.content.decode("utf-8"))["subject_token"][0]
        return {"access_token": f"exchanged-for-{subject}", "expires_in": 300}

    auth = _build_static_auth(fetch_json=fetch_json)

    with bind_current_authorization_header("Bearer subject-a"):
        prepared_grant_a = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
        async with auth._access_token_cache_locks[prepared_grant_a.cache_key]:  # pyright: ignore[reportPrivateUsage]
            _ = await auth._fetch_and_cache_token(prepared_grant_a)  # pyright: ignore[reportPrivateUsage]
    with bind_current_authorization_header("Bearer subject-b"):
        prepared_grant_b = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
        async with auth._access_token_cache_locks[prepared_grant_b.cache_key]:  # pyright: ignore[reportPrivateUsage]
            _ = await auth._fetch_and_cache_token(prepared_grant_b)  # pyright: ignore[reportPrivateUsage]

    assert prepared_grant_a.cache_key != prepared_grant_b.cache_key
    assert (
        auth._access_token_cache[prepared_grant_a.cache_key].access_token
        == "exchanged-for-subject-a"
    )  # pyright: ignore[reportPrivateUsage]
    assert (
        auth._access_token_cache[prepared_grant_b.cache_key].access_token
        == "exchanged-for-subject-b"
    )  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_exchange_token_evicts_expired_entries_on_fetch() -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "fresh", "expires_in": 300}

    auth = _build_static_auth(fetch_json=fetch_json)

    stale_key = _cache_key("stale-subject")
    auth._access_token_cache[stale_key] = AccessTokenInfo(  # pyright: ignore[reportPrivateUsage]
        "stale-token",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    with bind_current_authorization_header("Bearer fresh-subject"):
        prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
        async with auth._access_token_cache_locks[prepared_grant.cache_key]:  # pyright: ignore[reportPrivateUsage]
            _ = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]

    assert stale_key not in auth._access_token_cache  # pyright: ignore[reportPrivateUsage]
    assert prepared_grant.cache_key in auth._access_token_cache  # pyright: ignore[reportPrivateUsage]


# --- end-to-end auth flow ----------------------------------------------------


@pytest.mark.asyncio
async def test_async_auth_flow_exchanges_using_subject_token_from_context() -> None:
    exchanged_subjects: list[str] = []
    authorization_headers: list[str] = []

    async def fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        assert isinstance(url, httpx.Request)
        exchanged_subjects.append(
            parse_qs(url.content.decode("utf-8"))["subject_token"][0]
        )
        return {"access_token": "exchanged-token", "expires_in": 600}

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(200)

    auth = _build_static_auth(fetch_json=fetch_json)

    with bind_current_authorization_header("Bearer inbound-subject"):
        async with httpx.AsyncClient(
            auth=auth, transport=httpx.MockTransport(handler)
        ) as client:
            response = await client.get("https://mcp.example/resource")

    assert response.status_code == 200
    assert exchanged_subjects == ["inbound-subject"]
    assert authorization_headers == ["Bearer exchanged-token"]
    assert auth._access_token_cache[_cache_key("inbound-subject")].access_token == (  # pyright: ignore[reportPrivateUsage]
        "exchanged-token"
    )


@pytest.mark.asyncio
async def test_async_auth_flow_raises_when_no_subject_token_in_context() -> None:
    handler_called = False

    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        nonlocal handler_called
        handler_called = True
        return httpx.Response(200)

    auth = _build_static_auth()

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(ValueError, match="no inbound Authorization header"):
            _ = await client.get("https://mcp.example/resource")

    assert not handler_called
