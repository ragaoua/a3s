import pytest
from pydantic_core import Url

import src.mcp.core as mcp_core
from src.config.types import (
    McpServerConfig,
    McpServerOAuthClientCredentialsAuthConfig,
    McpServerOAuthTokenForwardAuthConfig,
)
from src.config.types.mcp_servers import McpServerOAuthDiscoveredTokenExchangeAuthConfig


def _patch_mcp_builders(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict]]:
    captured: dict[str, list[dict]] = {
        "connection_params": [],
        "toolsets": [],
    }

    def fake_connection_params(**kwargs):
        captured["connection_params"].append(kwargs)
        return {"kind": "connection_params", **kwargs}

    def fake_toolset(**kwargs):
        captured["toolsets"].append(kwargs)
        return {"kind": "toolset", **kwargs}

    monkeypatch.setattr(
        mcp_core, "StreamableHTTPConnectionParams", fake_connection_params
    )
    monkeypatch.setattr(mcp_core, "McpToolset", fake_toolset)

    return captured


def test_get_mcp_tool_set_builds_toolset_for_server_without_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_mcp_builders(monkeypatch)
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth="none",
        )
    ]

    toolsets = mcp_core.get_mcp_tool_set(config)

    assert captured["connection_params"] == [{"url": "https://mcp.example/server"}]
    assert captured["toolsets"] == [
        {
            "connection_params": {
                "kind": "connection_params",
                "url": "https://mcp.example/server",
            },
            "header_provider": None,
        }
    ]
    assert toolsets == [
        {
            "kind": "toolset",
            "connection_params": {
                "kind": "connection_params",
                "url": "https://mcp.example/server",
            },
            "header_provider": None,
        }
    ]


def test_get_mcp_tool_set_uses_header_provider_for_token_forward_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_mcp_builders(monkeypatch)
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth=McpServerOAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
        )
    ]

    toolsets = mcp_core.get_mcp_tool_set(config)

    assert captured["connection_params"] == [{"url": "https://mcp.example/server"}]
    assert captured["toolsets"] == [
        {
            "connection_params": {
                "kind": "connection_params",
                "url": "https://mcp.example/server",
            },
            "header_provider": mcp_core.oauth_token_forward_header_provider,
        }
    ]
    assert (
        toolsets[0]["header_provider"] is mcp_core.oauth_token_forward_header_provider
    )


def test_get_mcp_tool_set_uses_client_credentials_httpx_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_mcp_builders(monkeypatch)
    build_factory_calls: list[
        tuple[Url, McpServerOAuthClientCredentialsAuthConfig]
    ] = []
    factory = object()
    server_config = McpServerConfig(
        url=Url("https://mcp.example/server"),
        auth=McpServerOAuthClientCredentialsAuthConfig(
            mode="oauth_client_credentials",
            token_endpoint=Url("https://issuer.example/oauth/token"),
            client_id="client-id",
            client_secret="client-secret",
        ),
    )

    def fake_build_factory(server_url, server_auth_config):
        build_factory_calls.append((server_url, server_auth_config))
        return factory

    monkeypatch.setattr(
        mcp_core.OAuthClientCredentialsAuth,
        "build_factory",
        fake_build_factory,
    )

    toolsets = mcp_core.get_mcp_tool_set([server_config])

    assert build_factory_calls == [(server_config.url, server_config.auth)]
    assert captured["connection_params"] == [
        {
            "url": "https://mcp.example/server",
            "httpx_client_factory": factory,
        }
    ]
    assert captured["toolsets"] == [
        {
            "connection_params": {
                "kind": "connection_params",
                "url": "https://mcp.example/server",
                "httpx_client_factory": factory,
            },
            "header_provider": None,
        }
    ]
    assert toolsets[0]["connection_params"]["httpx_client_factory"] is factory


def test_get_mcp_tool_set_raises_for_token_exchange_auth() -> None:
    config = [
        McpServerConfig(
            url=Url("https://mcp.example/server"),
            auth=McpServerOAuthDiscoveredTokenExchangeAuthConfig(
                mode="oauth_token_exchange",
                client_id="client-id",
                client_secret="client-secret",
            ),
        )
    ]

    with pytest.raises(NotImplementedError, match="oauth_token_exchange"):
        mcp_core.get_mcp_tool_set(config)
