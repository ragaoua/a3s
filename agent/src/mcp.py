import base64
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request

import httpx
from google.adk.agents.llm_agent import ToolUnion
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from mcp.shared._httpx_utils import create_mcp_http_client
from pydantic_core import Url

from src.config.types import (
    McpServerConfig,
    McpServerOAuthClientCredentialsAuthConfig,
    McpServerOAuthTokenForwardAuthConfig,
)
from src.utils import fetch_json


MCP_SERVER_ACCESS_TOKEN_CACHE: dict[tuple[Url, str], str] = {}
CUSTOM_METADATA_TEMP_HEADERS_KEY = "temp:headers"


def get_mcp_tool_set(config: list[McpServerConfig]) -> list[ToolUnion]:
    mcp_tool_set = []

    header_provider = None
    for serverConfig in config:
        if isinstance(serverConfig.auth, McpServerOAuthClientCredentialsAuthConfig):
            connection_params = StreamableHTTPConnectionParams(
                url=str(serverConfig.url),
                httpx_client_factory=oauth_client_credentials_http_client_factory(
                    serverConfig.url, serverConfig.auth
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


def _fetch_mcp_server_access_token(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> str:
    body = {"grant_type": "client_credentials"}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    if server_auth_config.auth_method == "client_secret_basic":
        client_credentials = f"{server_auth_config.client_id}:{server_auth_config.client_secret.get_secret_value()}"
        headers["Authorization"] = "Basic " + base64.b64encode(
            client_credentials.encode("utf-8")
        ).decode("ascii")
    else:
        body["client_id"] = server_auth_config.client_id
        body["client_secret"] = server_auth_config.client_secret.get_secret_value()

    token_response = fetch_json(
        Request(
            str(server_auth_config.token_endpoint),
            data=urlencode(body).encode("utf-8"),
            headers=headers,
            method="POST",
        ),
        error_message=(
            f"Failed to fetch OAuth2 access token for MCP server '{server_url}'"
        ),
    )
    access_token = token_response.get("access_token")

    if not isinstance(access_token, str) or access_token == "":
        raise ValueError(
            "OAuth2 client credentials response is missing a valid 'access_token'"
        )

    return access_token


def _refresh_mcp_server_access_token(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> str:
    cache_key = (server_auth_config.token_endpoint, server_auth_config.client_id)
    MCP_SERVER_ACCESS_TOKEN_CACHE.pop(cache_key, None)

    access_token = _fetch_mcp_server_access_token(server_url, server_auth_config)
    MCP_SERVER_ACCESS_TOKEN_CACHE[cache_key] = access_token
    return access_token


def _get_mcp_server_access_token(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> str:
    cache_key = (server_auth_config.token_endpoint, server_auth_config.client_id)
    access_token = MCP_SERVER_ACCESS_TOKEN_CACHE.get(cache_key)

    if access_token is None:
        access_token = _fetch_mcp_server_access_token(server_url, server_auth_config)
        MCP_SERVER_ACCESS_TOKEN_CACHE[cache_key] = access_token

    return access_token


def _is_invalid_token_error(response: httpx.Response) -> bool:
    if response.status_code != 401:
        return False

    return any(
        "bearer" in header.lower() and "invalid_token" in header.lower()
        for header in response.headers.get_list("www-authenticate")
    )


class _McpServerOAuthClientCredentialsAuth(httpx.Auth):
    def __init__(
        self,
        server_url: Url,
        server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
    ):
        self._server_url = server_url
        self._server_auth_config = server_auth_config

    async def async_auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = "Bearer " + _get_mcp_server_access_token(
            self._server_url, self._server_auth_config
        )
        response = yield request

        if not _is_invalid_token_error(response):
            return

        request.headers["Authorization"] = "Bearer " + _refresh_mcp_server_access_token(
            self._server_url, self._server_auth_config
        )
        yield request


def oauth_client_credentials_http_client_factory(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> Callable[
    [dict[str, str] | None, httpx.Timeout | None, httpx.Auth | None],
    httpx.AsyncClient,
]:
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
                    server_url, server_auth_config
                )
            ),
        )

    return factory
