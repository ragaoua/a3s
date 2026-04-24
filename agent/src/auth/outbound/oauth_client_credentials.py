import asyncio
import base64
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import override
from urllib.parse import urlencode

import httpx
from mcp.shared._httpx_utils import create_mcp_http_client
from pydantic_core import Url

from src.config.types import OAuthClientCredentialsAuthConfig
from src.auth.outbound.internal.types import AccessTokenCacheKey, AccessTokenInfo
from src.utils import fetch_json
from src.auth.outbound.internal.token_helpers import get_access_token_expiry_date


class OAuthClientCredentialsAuth(httpx.Auth):
    _ACCESS_TOKEN_CACHE: dict[
        AccessTokenCacheKey,
        AccessTokenInfo,
    ] = {}
    _ACCESS_TOKEN_CACHE_LOCKS: dict[
        AccessTokenCacheKey,
        asyncio.Lock,
    ] = {}

    # NOTE: this could be configurable by the client, or it
    # could be more dynamic (percentage of the token's TTL)
    _ACCESS_TOKEN_REFRESH_WINDOW: timedelta = timedelta(seconds=30)

    def __init__(
        self,
        server_url: Url,
        server_auth_config: OAuthClientCredentialsAuthConfig,
    ):
        self._server_url: Url = server_url
        self._server_auth_config: OAuthClientCredentialsAuthConfig = server_auth_config
        self._cache_key: AccessTokenCacheKey = AccessTokenCacheKey(
            server_auth_config.token_endpoint,
            server_auth_config.client_id,
        )

    @staticmethod
    def build_factory(
        server_url: Url,
        server_auth_config: OAuthClientCredentialsAuthConfig,
    ):
        def factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            return create_mcp_http_client(
                headers=headers,
                timeout=timeout,
                auth=(
                    auth
                    if auth is not None
                    else OAuthClientCredentialsAuth(
                        server_url,
                        server_auth_config,
                    )
                ),
            )

        return factory

    @override
    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        should_retry = False

        async with self._ACCESS_TOKEN_CACHE_LOCKS.setdefault(
            self._cache_key, asyncio.Lock()
        ):
            cached_token_info = self._ACCESS_TOKEN_CACHE.get(self._cache_key)

            # Token not in cache: fetch fresh one from auth server
            if cached_token_info is None:
                token_info = await self.fetch_access_token_from_auth_server()

            # Token expired or almost expired: fetch new one.
            # If fetch fails, use cached token if not completely expired.
            # In that case, we don't want to retry if the request fails later,
            # because even if we are using a cached token, the remote refresh
            # failed.
            elif (
                cached_token_info.expires_at is not None
                and cached_token_info.expires_at
                <= (datetime.now(timezone.utc) + self._ACCESS_TOKEN_REFRESH_WINDOW)
            ):
                try:
                    token_info = await self.fetch_access_token_from_auth_server()
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

        if self.isUnauthorizedBearer(response):
            # If the token we used what in cache, fetch a new one from the auth
            # server and retry (in case the token was revoked/has expired etc
            # since we cached it).
            if should_retry:
                async with self._ACCESS_TOKEN_CACHE_LOCKS.setdefault(
                    self._cache_key, asyncio.Lock()
                ):
                    cached_token_info = self._ACCESS_TOKEN_CACHE.get(self._cache_key)
                    if token_info == cached_token_info or cached_token_info is None:
                        try:
                            token_info = (
                                await self.fetch_access_token_from_auth_server()
                            )
                        except Exception:
                            _ = self._ACCESS_TOKEN_CACHE.pop(self._cache_key, None)
                            raise
                    else:
                        token_info = cached_token_info

                request.headers["Authorization"] = "Bearer " + token_info.access_token
                response = yield request

                if not self.isUnauthorizedBearer(response):
                    return

            async with self._ACCESS_TOKEN_CACHE_LOCKS.setdefault(
                self._cache_key, asyncio.Lock()
            ):
                if token_info == self._ACCESS_TOKEN_CACHE.get(self._cache_key):
                    _ = self._ACCESS_TOKEN_CACHE.pop(self._cache_key, None)

    def isUnauthorizedBearer(self, response: httpx.Response):
        return response.status_code == 401 and any(
            "bearer" in header.lower()
            for header in response.headers.get_list("www-authenticate")
        )

    async def fetch_access_token_from_auth_server(self) -> AccessTokenInfo:
        lock = self._ACCESS_TOKEN_CACHE_LOCKS.get(self._cache_key)
        if lock is None or not lock.locked():
            raise RuntimeError(
                "The access token cache lock must be acquired first since this method updates the cache upon fetching a fresh token from the authorization server"
            )

        body = {"grant_type": "client_credentials"}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        if self._server_auth_config.auth_method == "client_secret_basic":
            client_credentials = f"{self._server_auth_config.client_id}:{self._server_auth_config.client_secret.get_secret_value()}"
            headers["Authorization"] = "Basic " + base64.b64encode(
                client_credentials.encode("utf-8")
            ).decode("ascii")
        else:
            body["client_id"] = self._server_auth_config.client_id
            body["client_secret"] = (
                self._server_auth_config.client_secret.get_secret_value()
            )

        token_response = await fetch_json(
            httpx.Request(
                method="POST",
                url=str(self._server_auth_config.token_endpoint),
                headers=headers,
                content=urlencode(body).encode("utf-8"),
            ),
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
