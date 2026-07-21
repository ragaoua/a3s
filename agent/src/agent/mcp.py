import httpx
from google.adk.agents.llm_agent import ToolUnion
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from mcp.shared._httpx_utils import create_mcp_http_client
from pydantic_core import Url

from src.auth.context import get_current_authorization_header
from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import (
    McpServerConfig,
    OAuthClientCredentialsAuthConfig,
    OAuthTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
)


def get_mcp_toolsets(config: list[McpServerConfig]) -> list[ToolUnion]:
    mcp_toolset = []

    for server_config in config:
        header_provider = None
        if isinstance(server_config.auth, OAuthClientCredentialsAuthConfig):
            connection_params = StreamableHTTPConnectionParams(
                url=str(server_config.url),
                httpx_client_factory=_build_oauth_client_credentials_mcp_client_factory(
                    server_config.url,
                    server_config.auth,
                ),
            )
        elif isinstance(server_config.auth, OAuthTokenExchangeAuthConfig):
            raise NotImplementedError(
                "mcp_servers[].auth.mode='oauth_token_exchange' is not implemented yet"
            )
        else:
            connection_params = StreamableHTTPConnectionParams(
                url=str(server_config.url)
            )
            if isinstance(server_config.auth, OAuthTokenForwardAuthConfig):
                header_provider = _oauth_token_forward_header_provider

        mcp_toolset.append(
            McpToolset(
                connection_params=connection_params,
                header_provider=header_provider,
            )
        )

    return mcp_toolset


def _oauth_token_forward_header_provider(
    _: ReadonlyContext | None = None,
) -> dict[str, str]:
    authorization_header = get_current_authorization_header()
    if not authorization_header:
        return {}

    return {"Authorization": authorization_header}


def _build_oauth_client_credentials_mcp_client_factory(
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
