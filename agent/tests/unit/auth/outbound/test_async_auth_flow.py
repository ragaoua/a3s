from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.auth.outbound.types import AccessTokenInfo
from tests.unit.auth.outbound.conftest import BuildGrantAuth


def _bearer_401() -> httpx.Response:
    return httpx.Response(401, headers={"WWW-Authenticate": "Bearer realm=test"})


def _valid_token_info(access_token: str) -> AccessTokenInfo:
    return AccessTokenInfo(
        access_token,
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )


@pytest.mark.asyncio
async def test_async_auth_flow_fetches_and_uses_token_when_cache_empty(
    build_auth: BuildGrantAuth,
) -> None:
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        return _valid_token_info("fresh-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(200)

    auth = build_auth(fetch=fetch)

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == ["Bearer fresh-token"]


@pytest.mark.asyncio
async def test_async_auth_flow_uses_cached_token_without_fetching_when_not_in_refresh_window(
    build_auth: BuildGrantAuth,
) -> None:
    authorization_headers: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(200)

    auth = build_auth()
    cached = _valid_token_info("cached-token")
    auth._access_token_cache[auth._cache_key] = cached  # pyright: ignore[reportPrivateUsage]

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == ["Bearer cached-token"]
    assert auth._access_token_cache[auth._cache_key] is cached  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_refreshes_cached_token_when_in_refresh_window(
    build_auth: BuildGrantAuth,
) -> None:
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        return _valid_token_info("fresh-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(200)

    auth = build_auth(fetch=fetch)
    auth._access_token_cache[auth._cache_key] = AccessTokenInfo(  # pyright: ignore[reportPrivateUsage]
        "soon-expired-token",
        datetime.now(timezone.utc) + timedelta(seconds=15),
    )

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == ["Bearer fresh-token"]


@pytest.mark.asyncio
async def test_async_auth_flow_falls_back_to_cached_token_when_refresh_fails_and_token_still_valid(
    build_auth: BuildGrantAuth,
) -> None:
    fetch_called = False
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        nonlocal fetch_called
        fetch_called = True
        raise RuntimeError("refresh failed")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return httpx.Response(200)

    auth = build_auth(fetch=fetch)
    soon_expired = AccessTokenInfo(
        "soon-expired-token",
        datetime.now(timezone.utc) + timedelta(seconds=15),
    )
    auth._access_token_cache[auth._cache_key] = soon_expired  # pyright: ignore[reportPrivateUsage]

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert fetch_called
    assert authorization_headers == ["Bearer soon-expired-token"]
    assert auth._access_token_cache[auth._cache_key] is soon_expired  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_raises_when_cached_token_expired_and_refresh_fails(
    build_auth: BuildGrantAuth,
) -> None:
    handler_called = False

    async def fetch() -> AccessTokenInfo:
        raise RuntimeError("refresh failed")

    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        nonlocal handler_called
        handler_called = True
        return httpx.Response(200)

    auth = build_auth(fetch=fetch)
    auth._access_token_cache[auth._cache_key] = AccessTokenInfo(  # pyright: ignore[reportPrivateUsage]
        "expired-token",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(RuntimeError, match="refresh failed"):
            _ = await client.get("https://api.example/resource")

    assert not handler_called


@pytest.mark.asyncio
async def test_async_auth_flow_retries_with_fresh_token_when_cached_token_gets_401_bearer(
    build_auth: BuildGrantAuth,
) -> None:
    fetch_calls = 0
    authorization_headers: list[str] = []
    responses: list[httpx.Response] = [_bearer_401(), httpx.Response(200)]

    async def fetch() -> AccessTokenInfo:
        nonlocal fetch_calls
        fetch_calls += 1
        return _valid_token_info("fresh-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return responses.pop(0)

    auth = build_auth(fetch=fetch)
    auth._access_token_cache[auth._cache_key] = _valid_token_info("cached-token")  # pyright: ignore[reportPrivateUsage]

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == ["Bearer cached-token", "Bearer fresh-token"]
    assert fetch_calls == 1
    assert auth._access_token_cache[auth._cache_key].access_token == "fresh-token"  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_invalidates_cache_after_initial_token_fetch_on_401_bearer(
    build_auth: BuildGrantAuth,
) -> None:
    fetch_calls = 0
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        nonlocal fetch_calls
        fetch_calls += 1
        return _valid_token_info("fresh-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return _bearer_401()

    auth = build_auth(fetch=fetch)

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 401
    assert authorization_headers == ["Bearer fresh-token"]
    assert fetch_calls == 1
    assert auth._cache_key not in auth._access_token_cache  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_invalidates_cache_when_retry_also_gets_401_bearer(
    build_auth: BuildGrantAuth,
) -> None:
    fetch_calls = 0
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        nonlocal fetch_calls
        fetch_calls += 1
        return _valid_token_info("fresh-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return _bearer_401()

    auth = build_auth(fetch=fetch)
    auth._access_token_cache[auth._cache_key] = _valid_token_info("cached-token")  # pyright: ignore[reportPrivateUsage]

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 401
    assert authorization_headers == ["Bearer cached-token", "Bearer fresh-token"]
    assert fetch_calls == 1
    assert auth._cache_key not in auth._access_token_cache  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_invalidates_cache_and_raises_when_retry_refresh_fails(
    build_auth: BuildGrantAuth,
) -> None:
    authorization_headers: list[str] = []

    async def fetch() -> AccessTokenInfo:
        raise RuntimeError("refresh failed")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        return _bearer_401()

    auth = build_auth(fetch=fetch)
    auth._access_token_cache[auth._cache_key] = _valid_token_info("cached-token")  # pyright: ignore[reportPrivateUsage]

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(RuntimeError, match="refresh failed"):
            _ = await client.get("https://api.example/resource")

    assert authorization_headers == ["Bearer cached-token"]
    assert auth._cache_key not in auth._access_token_cache  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_async_auth_flow_uses_externally_refreshed_token_on_retry_without_refetching(
    build_auth: BuildGrantAuth,
) -> None:
    authorization_headers: list[str] = []
    responses: list[httpx.Response] = [_bearer_401(), httpx.Response(200)]

    auth = build_auth()
    auth._access_token_cache[auth._cache_key] = _valid_token_info("cached-token")  # pyright: ignore[reportPrivateUsage]
    externally_refreshed = _valid_token_info("externally-refreshed-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers["Authorization"])
        response = responses.pop(0)
        if response.status_code == 401:
            auth._access_token_cache[auth._cache_key] = externally_refreshed  # pyright: ignore[reportPrivateUsage]
        return response

    async with httpx.AsyncClient(
        auth=auth, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get("https://api.example/resource")

    assert response.status_code == 200
    assert authorization_headers == [
        "Bearer cached-token",
        "Bearer externally-refreshed-token",
    ]
    assert auth._access_token_cache[auth._cache_key] is externally_refreshed  # pyright: ignore[reportPrivateUsage]
