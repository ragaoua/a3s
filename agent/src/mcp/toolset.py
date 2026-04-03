from google.adk.agents.llm_agent import ToolUnion
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from src.config.types import (
    McpServerConfig,
    McpServerOAuthClientCredentialsAuthConfig,
    McpServerOAuthTokenExchangeAuthConfig,
    McpServerOAuthTokenForwardAuthConfig,
)

from .headers import oauth_token_forward_header_provider
from .oauth_client_credentials import oauth_client_credentials_http_client_factory


def get_mcp_tool_set(config: list[McpServerConfig]) -> list[ToolUnion]:
    mcp_tool_set = []

    for server_config in config:
        header_provider = None
        if isinstance(server_config.auth, McpServerOAuthClientCredentialsAuthConfig):
            connection_params = StreamableHTTPConnectionParams(
                url=str(server_config.url),
                httpx_client_factory=oauth_client_credentials_http_client_factory(
                    server_config.url,
                    server_config.auth,
                ),
            )
        elif isinstance(server_config.auth, McpServerOAuthTokenExchangeAuthConfig):
            raise NotImplementedError(
                "mcp_servers[].auth.mode='oauth_token_exchange' is not implemented yet"
            )
        else:
            connection_params = StreamableHTTPConnectionParams(
                url=str(server_config.url)
            )
            if isinstance(server_config.auth, McpServerOAuthTokenForwardAuthConfig):
                header_provider = oauth_token_forward_header_provider

        mcp_tool_set.append(
            McpToolset(
                connection_params=connection_params,
                header_provider=header_provider,
            )
        )

    return mcp_tool_set
