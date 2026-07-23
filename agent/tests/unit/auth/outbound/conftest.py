from collections.abc import Awaitable, Callable, Generator
from typing import Protocol, override

import pytest

from src.auth.outbound.oauth_grant import OAuthGrantAuth
from src.auth.outbound.types import AccessTokenInfo, PreparedGrant
from src.config.types import OAuthClientAuthConfig


class _FakeGrantAuth(OAuthGrantAuth[str, OAuthClientAuthConfig]):
    """Minimal concrete grant used to exercise the base OAuthGrantAuth behavior
    (fetch-and-cache, proactive refresh, retry) on its own, without depending on
    any real grant's token request.

    `_prepare_grant` hands back a caller-supplied `fetch`, so tests control
    exactly what the grant produces and assert only on base-class behavior;
    token parsing/expiry belongs to each concrete grant's own tests."""

    def __init__(  # pyright: ignore[reportMissingSuperCall]
        self,
        cache_key: str,
        fetch: Callable[[], Awaitable[AccessTokenInfo]],
    ) -> None:
        self._cache_key: str = cache_key
        self._fetch: Callable[[], Awaitable[AccessTokenInfo]] = fetch

    @override
    async def _prepare_grant(self) -> PreparedGrant[str]:
        return PreparedGrant(self._cache_key, self._fetch)


class BuildGrantAuth(Protocol):
    def __call__(
        self,
        *,
        fetch: Callable[[], Awaitable[AccessTokenInfo]] | None = None,
        cache_key: str = "cache-key",
    ) -> _FakeGrantAuth: ...


@pytest.fixture(autouse=True)
def clear_access_token_cache() -> Generator[None, None, None]:
    _FakeGrantAuth._access_token_cache.clear()  # pyright: ignore[reportPrivateUsage]
    _FakeGrantAuth._access_token_cache_locks.clear()  # pyright: ignore[reportPrivateUsage]
    yield


@pytest.fixture
def build_auth() -> BuildGrantAuth:
    async def _default_fetch() -> AccessTokenInfo:
        raise AssertionError("the grant fetch must not be called")

    def _build(
        *,
        fetch: Callable[[], Awaitable[AccessTokenInfo]] | None = None,
        cache_key: str = "cache-key",
    ) -> _FakeGrantAuth:
        return _FakeGrantAuth(cache_key, fetch or _default_fetch)

    return _build
