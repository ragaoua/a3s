import base64
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request
from google.adk.agents.llm_agent import ToolUnion
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
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
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=str(serverConfig.url),
            ),
            header_provider=get_mcp_server_header_provider(serverConfig),
        )
        for serverConfig in config
    ]


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


def oauth_client_credentials_header_provider(
    server_url: Url,
    server_auth_config: McpServerOAuthClientCredentialsAuthConfig,
) -> Callable[[ReadonlyContext], dict[str, str]]:
    cache_key = (server_auth_config.token_endpoint, server_auth_config.client_id)

    def provider(_ctx: ReadonlyContext) -> dict[str, str]:
        access_token = MCP_SERVER_ACCESS_TOKEN_CACHE.get(cache_key)
        if access_token is None:
            access_token = _fetch_mcp_server_access_token(
                server_url, server_auth_config
            )
            MCP_SERVER_ACCESS_TOKEN_CACHE[cache_key] = access_token

        return {"Authorization": f"Bearer {access_token}"}

    return provider


def get_mcp_server_header_provider(
    server: McpServerConfig,
) -> Callable[[ReadonlyContext], dict[str, str]] | None:
    if isinstance(server.auth, McpServerOAuthTokenForwardAuthConfig):
        return oauth_token_forward_header_provider

    if isinstance(server.auth, McpServerOAuthClientCredentialsAuthConfig):
        return oauth_client_credentials_header_provider(server.url, server.auth)

    return None
