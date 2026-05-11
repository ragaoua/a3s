from datetime import datetime, timedelta, timezone

import httpx
from pydantic import JsonValue
import pytest

from src.auth.outbound.types import AccessTokenInfo
from tests.unit.auth.outbound.conftest import BuildAuth


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_raises_when_lock_not_acquired(
    build_auth: BuildAuth,
) -> None:
    auth = build_auth()

    with pytest.raises(RuntimeError, match="cache lock must be acquired first"):
        _ = await auth._fetch_access_token_from_auth_server()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_returns_and_caches_token(
    build_auth: BuildAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "token-123", "expires_in": 60}

    auth = build_auth(fetch_json=fetch_json)
    before = datetime.now(timezone.utc)

    async with auth._ACCESS_TOKEN_CACHE_LOCKS[auth._cache_key]:  # pyright: ignore[reportPrivateUsage]
        token_info = await auth._fetch_access_token_from_auth_server()  # pyright: ignore[reportPrivateUsage]

    after = datetime.now(timezone.utc)

    assert token_info.access_token == "token-123"
    assert token_info.expires_at is not None and (
        before + timedelta(seconds=60)
        <= token_info.expires_at
        <= after + timedelta(seconds=60)
    )
    assert auth._ACCESS_TOKEN_CACHE[auth._cache_key] is token_info  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_propagates_fetch_json_error(
    build_auth: BuildAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,
        error_message: str | None = None,
    ) -> dict[str, JsonValue]:
        raise error_cls(error_message)

    auth = build_auth(fetch_json=fetch_json)

    async with auth._ACCESS_TOKEN_CACHE_LOCKS[auth._cache_key]:  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(
            ValueError,
            match="Failed to fetch OAuth2 access token for server 'https://mcp.example/'",
        ):
            _ = await auth._fetch_access_token_from_auth_server()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_fetch_access_token_from_auth_server_returns_token_with_none_expiry_when_expires_in_missing(
    build_auth: BuildAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "token-123"}

    auth = build_auth(fetch_json=fetch_json)

    async with auth._ACCESS_TOKEN_CACHE_LOCKS[auth._cache_key]:  # pyright: ignore[reportPrivateUsage]
        token_info = await auth._fetch_access_token_from_auth_server()  # pyright: ignore[reportPrivateUsage]

    assert token_info == AccessTokenInfo("token-123", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("access_token", [None, "", 123])
async def test_fetch_access_token_from_auth_server_rejects_invalid_access_token_type(
    access_token: JsonValue,
    build_auth: BuildAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": access_token}

    auth = build_auth(fetch_json=fetch_json)

    async with auth._ACCESS_TOKEN_CACHE_LOCKS[auth._cache_key]:  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(
            ValueError,
            match="missing a valid 'access_token'",
        ):
            _ = await auth._fetch_access_token_from_auth_server()  # pyright: ignore[reportPrivateUsage]
