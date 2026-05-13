from pydantic import SecretStr
import pytest
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from pydantic_core import Url

from src.agent import mcp
from src.agent.mcp import get_mcp_toolsets
from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import (
    McpServerConfig,
    OAuthClientCredentialsAuthConfig,
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
)


def _assert_is_toolset(tool: object) -> McpToolset:
    assert isinstance(tool, McpToolset)
    return tool


def _get_connection_params(toolset: McpToolset) -> StreamableHTTPConnectionParams:
    params = toolset._connection_params  # pyright: ignore[reportPrivateUsage]
    assert isinstance(params, StreamableHTTPConnectionParams)
    return params


def test_get_mcp_toolset_returns_empty_for_empty_config() -> None:
    assert get_mcp_toolsets([]) == []


def test_get_mcp_toolset_no_auth_builds_toolset_without_header_provider() -> None:
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth="none",
        )
    ]

    toolsets = get_mcp_toolsets(config)

    assert len(toolsets) == 1
    toolsets = _assert_is_toolset(toolsets[0])
    params = _get_connection_params(toolsets)
    assert params.url == "https://mcp.example/server"
    assert toolsets._header_provider is None  # pyright: ignore[reportPrivateUsage]


def test_get_mcp_toolset_token_forward_auth_wires_token_forward_header_provider() -> (
    None
):
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth=OAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
        )
    ]

    toolsets = get_mcp_toolsets(config)

    toolset = _assert_is_toolset(toolsets[0])
    params = _get_connection_params(toolset)
    assert params.url == "https://mcp.example/server"
    assert (
        toolset._header_provider  # pyright: ignore[reportPrivateUsage]
        is mcp._oauth_token_forward_header_provider  # pyright: ignore[reportPrivateUsage]
    )


def test_get_mcp_toolset_client_credentials_auth_installs_httpx_factory_bound_to_config() -> (
    None
):
    auth_config = OAuthClientCredentialsAuthConfig(
        mode="oauth_client_credentials",
        token_endpoint=Url("https://issuer.example/oauth/token"),
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
    )
    server_config = McpServerConfig(
        url=Url("https://mcp.example/server"),
        auth=auth_config,
    )

    toolsets = get_mcp_toolsets([server_config])

    toolset = _assert_is_toolset(toolsets[0])
    params = _get_connection_params(toolset)
    assert params.url == "https://mcp.example/server"
    assert toolset._header_provider is None  # pyright: ignore[reportPrivateUsage]

    factory = params.httpx_client_factory
    built_client = factory()
    assert isinstance(built_client.auth, OAuthClientCredentialsAuth)
    assert built_client.auth._server_url == server_config.url  # pyright: ignore[reportPrivateUsage]
    assert built_client.auth._server_auth_config is auth_config  # pyright: ignore[reportPrivateUsage]


def test_get_mcp_toolset_token_exchange_auth_raises_not_implemented() -> None:
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth=OAuthDiscoveredTokenExchangeAuthConfig(
                mode="oauth_token_exchange",
                client_id="client-id",
                client_secret=SecretStr("client-secret"),
            ),
        )
    ]

    with pytest.raises(NotImplementedError, match="oauth_token_exchange"):
        get_mcp_toolsets(config)


def test_get_mcp_toolset_preserves_order_across_multiple_servers() -> None:
    config = [
        McpServerConfig(
            url=Url("https://a.example/server"),
            auth="none",
        ),
        McpServerConfig(
            url=Url("https://b.example/server"),
            auth=OAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
        ),
        McpServerConfig(
            url=Url("https://c.example/server"),
            auth=OAuthClientCredentialsAuthConfig(
                mode="oauth_client_credentials",
                token_endpoint=Url("https://issuer.example/oauth/token"),
                client_id="client-id",
                client_secret=SecretStr("client-secret"),
            ),
        ),
    ]

    toolsets = get_mcp_toolsets(config)

    urls = [_get_connection_params(_assert_is_toolset(t)).url for t in toolsets]
    assert urls == [
        "https://a.example/server",
        "https://b.example/server",
        "https://c.example/server",
    ]
