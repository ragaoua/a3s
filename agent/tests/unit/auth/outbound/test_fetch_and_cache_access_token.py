from datetime import datetime, timedelta, timezone

import httpx
from pydantic import JsonValue
import pytest

from src.auth.outbound.types import AccessTokenInfo
from tests.unit.auth.outbound.conftest import BuildGrantAuth


@pytest.mark.asyncio
async def test_fetch_and_cache_token_raises_when_lock_not_acquired(
    build_auth: BuildGrantAuth,
) -> None:
    auth = build_auth()
    prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(RuntimeError, match="cache lock must be acquired first"):
        _ = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_fetch_and_cache_token_returns_and_caches_token(
    build_auth: BuildGrantAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "token-123", "expires_in": 60}

    auth = build_auth(fetch_json=fetch_json)
    prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]
    before = datetime.now(timezone.utc)

    async with auth._access_token_cache_locks[prepared_grant.cache_key]:  # pyright: ignore[reportPrivateUsage]
        token_info = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]

    after = datetime.now(timezone.utc)

    assert token_info.access_token == "token-123"
    assert token_info.expires_at is not None and (
        before + timedelta(seconds=60)
        <= token_info.expires_at
        <= after + timedelta(seconds=60)
    )
    assert auth._access_token_cache[prepared_grant.cache_key] is token_info  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_request_token_propagates_fetch_json_error(
    build_auth: BuildGrantAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,
        error_message: str | None = None,
    ) -> dict[str, JsonValue]:
        raise error_cls(error_message)

    auth = build_auth(fetch_json=fetch_json)

    with pytest.raises(
        ValueError,
        match="Failed to fetch OAuth2 access token for server 'https://mcp.example/'",
    ):
        _ = await auth._request_token()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_request_token_returns_token_with_none_expiry_when_expires_in_missing(
    build_auth: BuildGrantAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "token-123"}

    auth = build_auth(fetch_json=fetch_json)

    token_info = await auth._request_token()  # pyright: ignore[reportPrivateUsage]

    assert token_info == AccessTokenInfo("token-123", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("access_token", [None, "", 123])
async def test_request_token_rejects_invalid_access_token_type(
    access_token: JsonValue,
    build_auth: BuildGrantAuth,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": access_token}

    auth = build_auth(fetch_json=fetch_json)

    with pytest.raises(
        ValueError,
        match="missing a valid 'access_token'",
    ):
        _ = await auth._request_token()  # pyright: ignore[reportPrivateUsage]
