import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import override

import httpx
from pydantic_core import Url

from src.auth.outbound.token_expiry import get_access_token_expiry_date
from src.config.types import OAuthClientCredentialsAuthConfig
from src.auth.oauth_client_auth import build_client_authenticated_request
from src.auth.outbound.types import AccessTokenCacheKey, AccessTokenInfo
from src.utils import FetchJson, fetch_json


class OAuthClientCredentialsAuth(httpx.Auth):
    _ACCESS_TOKEN_CACHE: dict[
        AccessTokenCacheKey,
        AccessTokenInfo,
    ] = {}
    _ACCESS_TOKEN_CACHE_LOCKS: defaultdict[
        AccessTokenCacheKey,
        asyncio.Lock,
    ] = defaultdict(asyncio.Lock)

    # NOTE: this could be configurable by the client, or it
    # could be more dynamic (percentage of the token's TTL)
    _ACCESS_TOKEN_REFRESH_WINDOW: timedelta = timedelta(seconds=30)

    def __init__(
        self,
        server_url: Url,
        server_auth_config: OAuthClientCredentialsAuthConfig,
        *,
        fetch_json: FetchJson = fetch_json,
    ):
        self._server_url: Url = server_url
        self._server_auth_config: OAuthClientCredentialsAuthConfig = server_auth_config
        self._cache_key: AccessTokenCacheKey = AccessTokenCacheKey(
            server_auth_config.token_endpoint,
            server_auth_config.client_id,
        )
        self._fetch_json: FetchJson = fetch_json

    @override
    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        should_retry = False

        async with self._ACCESS_TOKEN_CACHE_LOCKS[self._cache_key]:
            cached_token_info = self._ACCESS_TOKEN_CACHE.get(self._cache_key)

            # Token not in cache: fetch fresh one from auth server
            if cached_token_info is None:
                token_info = await self._fetch_access_token_from_auth_server()

            # Token expired or almost expired: fetch new one.
            # If fetch fails, use cached token if not completely expired.
            # In that case, we don't want to retry (should_retry stays False)
            # if the request fails later, because even if we are using a cached
            # token, the remote refresh failed.
            elif (
                cached_token_info.expires_at is not None
                and cached_token_info.expires_at
                <= (datetime.now(timezone.utc) + self._ACCESS_TOKEN_REFRESH_WINDOW)
            ):
                try:
                    token_info = await self._fetch_access_token_from_auth_server()
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

        # If the token we used was in cache (and not soon expired),
        # fetch a new one from the auth server and retry (in case the token
        # was revoked/has expired etc since we cached it).
        if should_retry:
            async with self._ACCESS_TOKEN_CACHE_LOCKS[self._cache_key]:
                cached_token_info = self._ACCESS_TOKEN_CACHE.get(self._cache_key)
                if token_info == cached_token_info or cached_token_info is None:
                    try:
                        token_info = await self._fetch_access_token_from_auth_server()
                    except Exception:
                        _ = self._ACCESS_TOKEN_CACHE.pop(self._cache_key, None)
                        raise
                else:
                    token_info = cached_token_info

            request.headers["Authorization"] = "Bearer " + token_info.access_token
            response = yield request

            if not self._is_unauthorized_bearer(response):
                return

        async with self._ACCESS_TOKEN_CACHE_LOCKS[self._cache_key]:
            if token_info == self._ACCESS_TOKEN_CACHE.get(self._cache_key):
                _ = self._ACCESS_TOKEN_CACHE.pop(self._cache_key, None)

    @staticmethod
    def _is_unauthorized_bearer(response: httpx.Response):
        return response.status_code == 401 and any(
            "bearer" in header.lower()
            for header in response.headers.get_list("www-authenticate")
        )

    async def _fetch_access_token_from_auth_server(self) -> AccessTokenInfo:
        if not self._ACCESS_TOKEN_CACHE_LOCKS[self._cache_key].locked():
            raise RuntimeError(
                "The access token cache lock must be acquired first since this method updates the cache upon fetching a fresh token from the authorization server"
            )

        request = build_client_authenticated_request(
            url=str(self._server_auth_config.token_endpoint),
            body={"grant_type": "client_credentials"},
            auth_method=self._server_auth_config.auth_method,
            client_id=self._server_auth_config.client_id,
            client_secret=self._server_auth_config.client_secret,
        )
        token_response = await self._fetch_json(
            request,
            error_message=(
                f"Failed to fetch OAuth2 access token for server '{self._server_url}'"
            ),
        )
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or access_token == "":
            raise ValueError(
                "OAuth2 client credentials response is missing a valid 'access_token'"
            )

        access_token_info = AccessTokenInfo(
            access_token=access_token,
            expires_at=get_access_token_expiry_date(
                token_response,
                access_token,
            ),
        )
        self._ACCESS_TOKEN_CACHE[self._cache_key] = access_token_info
        return access_token_info
