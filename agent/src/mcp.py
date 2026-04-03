import base64
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple
from urllib.parse import urlencode
from urllib.request import Request

import httpx
import jwt
from google.adk.agents.llm_agent import ToolUnion
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from pydantic_core import Url

from src.config.types import (
    McpServerConfig,
    McpServerOAuthClientCredentialsAuthConfig,
    McpServerOAuthTokenForwardAuthConfig,
)
from src.utils import fetch_json


class _AccessTokenCacheKey(NamedTuple):
    token_endpoint: Url
    client_id: str


class _AccessTokenInfo(NamedTuple):
    access_token: str
    expires_at: datetime | None


ACCESS_TOKEN_CACHE: dict[
    _AccessTokenCacheKey,
    _AccessTokenInfo,
] = {}
# TODO: Maybe work on this
# - Should it be configurable ?
# - Should it be a percentage of the token's lifetime ?
# - ...
ACCESS_TOKEN_REFRESH_WINDOW = timedelta(seconds=30)

CUSTOM_METADATA_TEMP_HEADERS_KEY = "temp:headers"


def get_mcp_tool_set(config: list[McpServerConfig]) -> list[ToolUnion]:
    mcp_tool_set = []

    header_provider = None
    for serverConfig in config:
        if isinstance(serverConfig.auth, McpServerOAuthClientCredentialsAuthConfig):
            connection_params = StreamableHTTPConnectionParams(
                url=str(serverConfig.url),
                httpx_client_factory=oauth_client_credentials_http_client_factory(
                    serverConfig.url,
                    serverConfig.auth,
                ),
            )
        else:
            connection_params = StreamableHTTPConnectionParams(
                url=str(serverConfig.url)
            )
            if isinstance(serverConfig.auth, McpServerOAuthTokenForwardAuthConfig):
                header_provider = oauth_token_forward_header_provider

        mcp_tool_set.append(
            McpToolset(
                connection_params=connection_params,
                header_provider=header_provider,
            )
        )

    return mcp_tool_set


def oauth_token_forward_header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    if ctx.run_config is None or ctx.run_config.custom_metadata is None:
        return {}

    headers = ctx.run_config.custom_metadata[CUSTOM_METADATA_TEMP_HEADERS_KEY]
    if not headers:
        return {}

    authorization_header = {k: v for k, v in headers.items() if k == "authorization"}
    return authorization_header


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
        request.headers["Authorization"] = "Bearer " + self._get_access_token()
        response = yield request

        # If the token is invalid, we'll referesh it ONCE,
        # handling cases where the token has expired, has been
        # revoked, was issued with a secret key that's been rotated
        # since etc
        if response.status_code == 401 and any(
            "bearer" in header.lower() and "invalid_token" in header.lower()
            for header in response.headers.get_list("www-authenticate")
        ):
            request.headers["Authorization"] = (
                "Bearer " + self._invalidate_cache_and_refresh_access_token()
            )
            yield request

    def _get_access_token(self) -> str:
        cache_key = _AccessTokenCacheKey(
            self._server_auth_config.token_endpoint,
            self._server_auth_config.client_id,
        )
        token_info = ACCESS_TOKEN_CACHE.get(cache_key)

        if token_info is None:
            token_info = self._fetch_access_token()
            ACCESS_TOKEN_CACHE[cache_key] = token_info
            return token_info.access_token

        if token_info.expires_at is None or token_info.expires_at > (
            datetime.now(timezone.utc) + ACCESS_TOKEN_REFRESH_WINDOW
        ):
            return token_info.access_token

        try:
            refreshed_cache_entry = self._fetch_access_token()
            ACCESS_TOKEN_CACHE[cache_key] = refreshed_cache_entry
            return refreshed_cache_entry.access_token
        except Exception:
            if token_info.expires_at is None or token_info.expires_at > datetime.now(
                timezone.utc
            ):
                return token_info.access_token
            raise

    def _fetch_access_token(self) -> _AccessTokenInfo:
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

        token_response = fetch_json(
            Request(
                str(self._server_auth_config.token_endpoint),
                data=urlencode(body).encode("utf-8"),
                headers=headers,
                method="POST",
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

    def _invalidate_cache_and_refresh_access_token(self) -> str:
        cache_key = _AccessTokenCacheKey(
            self._server_auth_config.token_endpoint,
            self._server_auth_config.client_id,
        )
        _ = ACCESS_TOKEN_CACHE.pop(cache_key, None)

        token_info = self._fetch_access_token()
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
