import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, override

import httpx
from pydantic_core import Url

from src.auth.outbound.types import AccessTokenInfo, PreparedGrant
from src.config.types import OAuthClientAuthConfig
from src.utils import FetchJson, fetch_json


class OAuthGrantAuth[KeyT, ConfigT: OAuthClientAuthConfig](httpx.Auth, ABC):
    """Base for httpx auth flows that obtain a bearer token by running an OAuth2
    grant against a token endpoint, then cache, proactively refresh, and retry it.

    The template (`async_auth_flow`) is identical across grants; subclasses only
    supply the parts that actually differ:

    - `_prepared_grant`: read what this request needs.
    - `_evict_expired_tokens` (optional): prune stale entries before an insert,
      for grants whose cache is unbounded.

    The token cache is class-level (shared across all instances of a concrete
    subclass so tokens are reused across httpx clients and requests), and each
    subclass gets its own cache and lock table via `__init_subclass__` so that
    different grant types never share entries.
    """

    # Installed per concrete subclass by __init_subclass__ so each grant type
    # keeps an isolated cache. Keyed by Any because the key type varies per
    # subclass (KeyT); the typed surface is _prepare_grant's PreparedGrant.
    _access_token_cache: ClassVar[dict[Any, AccessTokenInfo]]
    _access_token_cache_locks: ClassVar[defaultdict[Any, asyncio.Lock]]

    # NOTE: this could be configurable by the client, or it could be more
    # dynamic (percentage of the token's TTL).
    _ACCESS_TOKEN_REFRESH_WINDOW: ClassVar[timedelta] = timedelta(seconds=30)

    def __init_subclass__(cls, **kwargs: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        super().__init_subclass__(**kwargs)
        cls._access_token_cache = {}
        cls._access_token_cache_locks = defaultdict(asyncio.Lock)

    def __init__(
        self,
        server_url: Url,
        server_auth_config: ConfigT,
        *,
        fetch_json: FetchJson = fetch_json,
    ):
        self._server_url: Url = server_url
        self._server_auth_config: ConfigT = server_auth_config
        self._fetch_json: FetchJson = fetch_json

    @abstractmethod
    async def _prepare_grant(self) -> PreparedGrant[KeyT]:
        """Read what the current request needs: the key its token is
        cached under, and a callable that runs the grant to fetch one."""
        pass

    async def _fetch_and_cache_token(
        self,
        prepared_grant: PreparedGrant[KeyT],
    ) -> AccessTokenInfo:
        """Run the grant for a fresh token and cache it under the prepared key."""
        cache_key = prepared_grant.cache_key
        if not self._access_token_cache_locks[cache_key].locked():
            raise RuntimeError(
                "The access token cache lock must be acquired first, since a "
                "freshly fetched token is written into the cache here"
            )

        token_info = await prepared_grant.fetch()

        # Let possibly unbounded caches prune stale entries before the insert.
        self._evict_expired_tokens()

        self._access_token_cache[cache_key] = token_info
        return token_info

    def _evict_expired_tokens(self) -> None:
        """Hook: prune stale entries before storing a freshly fetched token.

        A no-op by default — a grant whose set of cache keys is bounded never
        accumulates stale entries. Subclasses with a subject-token-scoped
        (unbounded) cache override this to evict."""

    @override
    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        prepared_grant = await self._prepare_grant()
        cache_key = prepared_grant.cache_key
        should_retry = False

        async with self._access_token_cache_locks[cache_key]:
            cached_token_info = self._access_token_cache.get(cache_key)

            # Token not in cache: fetch a fresh one from the auth server.
            if cached_token_info is None:
                token_info = await self._fetch_and_cache_token(prepared_grant)

            # Token expired or almost expired: fetch a new one.
            # If the fetch fails, fall back to the cached token if it's not
            # completely expired. In that case we don't retry on a 401 later
            # (should_retry stays False), since the remote refresh already failed.
            elif (
                cached_token_info.expires_at is not None
                and cached_token_info.expires_at
                <= (datetime.now(timezone.utc) + self._ACCESS_TOKEN_REFRESH_WINDOW)
            ):
                try:
                    token_info = await self._fetch_and_cache_token(prepared_grant)
                except Exception:
                    if cached_token_info.expires_at > datetime.now(timezone.utc):
                        token_info = cached_token_info
                    else:
                        raise

            # Token found in cache: use it.
            else:
                token_info = cached_token_info
                should_retry = True

        request.headers["Authorization"] = "Bearer " + token_info.access_token
        response = yield request

        if not self._is_unauthorized_bearer(response):
            return

        # If the token we used came from the cache (and wasn't soon to expire),
        # fetch a new one and retry (in case the token was revoked/expired since
        # we cached it).
        if should_retry:
            async with self._access_token_cache_locks[cache_key]:
                cached_token_info = self._access_token_cache.get(cache_key)
                if token_info == cached_token_info or cached_token_info is None:
                    try:
                        token_info = await self._fetch_and_cache_token(prepared_grant)
                    except Exception:
                        _ = self._access_token_cache.pop(cache_key, None)
                        raise
                else:
                    token_info = cached_token_info

            request.headers["Authorization"] = "Bearer " + token_info.access_token
            response = yield request

            if not self._is_unauthorized_bearer(response):
                return

        async with self._access_token_cache_locks[cache_key]:
            if token_info == self._access_token_cache.get(cache_key):
                _ = self._access_token_cache.pop(cache_key, None)

    @staticmethod
    def _is_unauthorized_bearer(response: httpx.Response) -> bool:
        return response.status_code == 401 and any(
            "bearer" in header.lower()
            for header in response.headers.get_list("www-authenticate")
        )
