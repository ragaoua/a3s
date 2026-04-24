from google.adk.agents.llm_agent import ToolUnion
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import (
    McpServerConfig,
    OAuthClientCredentialsAuthConfig,
    OAuthTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
)
from src.mcp.internal.headers import oauth_token_forward_header_provider


def get_mcp_tool_set(config: list[McpServerConfig]) -> list[ToolUnion]:
    mcp_tool_set = []

    for server_config in config:
        header_provider = None
        if isinstance(server_config.auth, OAuthClientCredentialsAuthConfig):
            connection_params = StreamableHTTPConnectionParams(
                url=str(server_config.url),
                httpx_client_factory=OAuthClientCredentialsAuth.build_factory(
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
                header_provider = oauth_token_forward_header_provider

        mcp_tool_set.append(
            McpToolset(
                connection_params=connection_params,
                header_provider=header_provider,
            )
        )

    return mcp_tool_set
