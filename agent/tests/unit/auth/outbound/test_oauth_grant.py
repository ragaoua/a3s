from datetime import datetime, timedelta, timezone

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
    token_info = AccessTokenInfo(
        "token-123",
        datetime.now(timezone.utc) + timedelta(seconds=60),
    )

    async def fetch() -> AccessTokenInfo:
        return token_info

    auth = build_auth(fetch=fetch)
    prepared_grant = await auth._prepare_grant()  # pyright: ignore[reportPrivateUsage]

    async with auth._access_token_cache_locks[prepared_grant.cache_key]:  # pyright: ignore[reportPrivateUsage]
        returned = await auth._fetch_and_cache_token(prepared_grant)  # pyright: ignore[reportPrivateUsage]

    assert returned is token_info
    assert auth._access_token_cache[prepared_grant.cache_key] is token_info  # pyright: ignore[reportPrivateUsage]
