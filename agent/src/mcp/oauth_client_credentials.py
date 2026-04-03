import base64
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple
from urllib.parse import urlencode

import httpx
import jwt
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from pydantic_core import Url

from src.config.types import McpServerOAuthClientCredentialsAuthConfig
from src.utils import fetch_json


class _AccessTokenCacheKey(NamedTuple):
    token_endpoint: Url
    client_id: str


class _AccessTokenInfo(NamedTuple):
    access_token: str
    expires_at: datetime | None


class _GetAccessTokenResult(NamedTuple):
    access_token: str
    fetched_from_cache: bool


ACCESS_TOKEN_CACHE: dict[
    _AccessTokenCacheKey,
    _AccessTokenInfo,
] = {}

# TODO: Maybe work on this
# - Should it be configurable ?
# - Should it be a percentage of the token's lifetime ?
# - ...
ACCESS_TOKEN_REFRESH_WINDOW = timedelta(seconds=30)


def _get_access_token_expiry_date(
    token_response: dict[str, Any],
    token: str,
) -> datetime | None:
    expires_in_raw = token_response.get("expires_in")
    expires_in: int | float | None = None

    if isinstance(expires_in_raw, (int, float)):
        if not isinstance(expires_in_raw, bool):
            expires_in = expires_in_raw
    elif isinstance(expires_in_raw, str):
        try:
            expires_in = float(expires_in_raw)
        except ValueError:
            pass

    if expires_in is not None:
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # No expires_in key in the token response. Try and
    # decode the token as a JWT to fetch the "exp" claim
    try:
        return _get_exp_datetime_from_jwt(token)
    except jwt.DecodeError:
        # Not a JWT, we can't know the expiry date.
        # We'll fallback to reactive token refreshing
        return None


def _get_exp_datetime_from_jwt(token: str) -> datetime | None:
    payload = jwt.decode(token, options={"verify_signature": False})
    exp = payload.get("exp")

    if isinstance(exp, (int, float)):
        if isinstance(exp, bool):
            return None

        try:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(exp, str):
        return None

    try:
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


class _McpServerOAuthClientCredentialsAuth(httpx.Auth):
    _server_url: Url
    _server_auth_config: McpServerOAuthClientCredentialsAuthConfig

    def __init__(
        self,
        server_url: Url,
        server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
    ):
        self._server_url = server_url
        self._server_auth_config = server_auth_config

    async def async_auth_flow(self, request: httpx.Request):
        access_token_result = await self._get_access_token()
        request.headers["Authorization"] = "Bearer " + access_token_result.access_token
        response = yield request

        # If a cached token is rejected, refresh it ONCE to handle
        # cases where it expired, was revoked, or server-side key
        # rotation invalidated it after it was cached locally.
        if (
            access_token_result.fetched_from_cache
            and response.status_code == 401
            and any(
                "bearer" in header.lower()
                for header in response.headers.get_list("www-authenticate")
            )
        ):
            request.headers["Authorization"] = (
                "Bearer " + await self._invalidate_cache_and_refresh_access_token()
            )
            yield request

    async def _get_access_token(self) -> _GetAccessTokenResult:
        cache_key = _AccessTokenCacheKey(
            self._server_auth_config.token_endpoint,
            self._server_auth_config.client_id,
        )
        token_info = ACCESS_TOKEN_CACHE.get(cache_key)

        if token_info is None:
            token_info = await self._fetch_access_token()
            ACCESS_TOKEN_CACHE[cache_key] = token_info
            return _GetAccessTokenResult(token_info.access_token, False)

        if token_info.expires_at is None or token_info.expires_at > (
            datetime.now(timezone.utc) + ACCESS_TOKEN_REFRESH_WINDOW
        ):
            return _GetAccessTokenResult(token_info.access_token, True)

        try:
            refreshed_cache_entry = await self._fetch_access_token()
            ACCESS_TOKEN_CACHE[cache_key] = refreshed_cache_entry
            return _GetAccessTokenResult(refreshed_cache_entry.access_token, False)
        except Exception:
            if token_info.expires_at is None or token_info.expires_at > datetime.now(
                timezone.utc
            ):
                return _GetAccessTokenResult(token_info.access_token, True)
            raise

    async def _fetch_access_token(self) -> _AccessTokenInfo:
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
                f"Failed to fetch OAuth2 access token for MCP server '{self._server_url}'"
            ),
        )
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or access_token == "":
            raise ValueError(
                "OAuth2 client credentials response is missing a valid 'access_token'"
            )

        return _AccessTokenInfo(
            access_token=access_token,
            expires_at=_get_access_token_expiry_date(
                token_response,
                access_token,
            ),
        )

    async def _invalidate_cache_and_refresh_access_token(self) -> str:
        cache_key = _AccessTokenCacheKey(
            self._server_auth_config.token_endpoint,
            self._server_auth_config.client_id,
        )
        _ = ACCESS_TOKEN_CACHE.pop(cache_key, None)

        token_info = await self._fetch_access_token()
        ACCESS_TOKEN_CACHE[cache_key] = token_info
        return token_info.access_token


def oauth_client_credentials_http_client_factory(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> McpHttpClientFactory:
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
                else _McpServerOAuthClientCredentialsAuth(
                    server_url,
                    server_auth_config,
                )
            ),
        )

    return factory
