from google.adk.agents import BaseAgent
import httpx
from pydantic import SecretStr
import pytest
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import agent_tool
from pydantic_core import Url

import src.agent.subagents as subagents_module
from src.agent.subagents import get_subagents
from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import (
    OAuthClientCredentialsAuthConfig,
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
    OutboundApiKeyAuthConfig,
    SubagentConfig,
)


def _assert_is_remote_agent(agent: BaseAgent) -> RemoteA2aAgent:
    assert isinstance(agent, RemoteA2aAgent)
    return agent


def _get_httpx_client(agent: RemoteA2aAgent) -> httpx.AsyncClient | None:
    return agent._a2a_client_factory._config.httpx_client  # pyright: ignore[reportPrivateUsage]


def _has_token_forward_interceptor(agent: RemoteA2aAgent) -> bool:
    config = agent._config  # pyright: ignore[reportPrivateUsage]
    if config is None:
        return False
    return any(
        interceptor.before_request is subagents_module._token_forward_before_request  # pyright: ignore[reportPrivateUsage]
        for interceptor in config.request_interceptors
    )


def test_get_subagents_returns_empty_for_empty_config() -> None:
    result = get_subagents({})

    assert result.delegate_subagents == []
    assert result.peer_subagents == []


def test_get_subagents_no_auth_creates_remote_agent_without_httpx_client() -> None:
    config = {
        "helper": SubagentConfig(
            url=Url("https://agent.example/api"),
            type="delegate",
            auth="none",
        )
    }

    result = get_subagents(config)

    assert len(result.delegate_subagents) == 1
    assert result.peer_subagents == []
    agent = _assert_is_remote_agent(result.delegate_subagents[0])
    assert agent.name == "helper"
    assert (
        agent._agent_card_source  # pyright: ignore[reportPrivateUsage]
        == "https://agent.example/api/.well-known/agent-card.json"
    )
    assert _get_httpx_client(agent) is None
    assert not _has_token_forward_interceptor(agent)
    assert agent._a2a_client_factory._config.streaming is True  # pyright: ignore[reportPrivateUsage]


def test_get_subagents_api_key_auth_sets_api_key_header_on_httpx_client() -> None:
    config = {
        "helper": SubagentConfig(
            url=Url("https://agent.example/api"),
            type="delegate",
            auth=OutboundApiKeyAuthConfig(
                mode="api_key", api_key=SecretStr("topsecret")
            ),
        )
    }

    result = get_subagents(config)

    agent = _assert_is_remote_agent(result.delegate_subagents[0])
    client = _get_httpx_client(agent)
    assert client is not None
    assert client.headers["API-Key"] == "topsecret"
    assert client.auth is None
    assert not _has_token_forward_interceptor(agent)


def test_get_subagents_client_credentials_auth_attaches_oauth_auth_to_httpx_client() -> (
    None
):
    auth_config = OAuthClientCredentialsAuthConfig(
        mode="oauth_client_credentials",
        token_endpoint=Url("https://issuer.example/oauth/token"),
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
    )
    subagent_config = SubagentConfig(
        url=Url("https://agent.example/api"),
        type="delegate",
        auth=auth_config,
    )

    result = get_subagents({"helper": subagent_config})

    agent = _assert_is_remote_agent(result.delegate_subagents[0])
    client = _get_httpx_client(agent)
    assert client is not None
    assert isinstance(client.auth, OAuthClientCredentialsAuth)
    assert client.auth._server_url == subagent_config.url  # pyright: ignore[reportPrivateUsage]
    assert client.auth._server_auth_config is auth_config  # pyright: ignore[reportPrivateUsage]
    assert not _has_token_forward_interceptor(agent)


def test_get_subagents_token_forward_registers_before_request_interceptor() -> None:
    config = {
        "helper": SubagentConfig(
            url=Url("https://agent.example/api"),
            type="delegate",
            auth=OAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
        )
    }

    result = get_subagents(config)

    agent = _assert_is_remote_agent(result.delegate_subagents[0])
    assert _get_httpx_client(agent) is None
    assert _has_token_forward_interceptor(agent)


def test_get_subagents_token_exchange_raises_not_implemented() -> None:
    config = {
        "helper": SubagentConfig(
            url=Url("https://agent.example/api"),
            type="delegate",
            auth=OAuthDiscoveredTokenExchangeAuthConfig(
                mode="oauth_token_exchange",
                client_id="client-id",
                client_secret=SecretStr("client-secret"),
            ),
        )
    }

    with pytest.raises(NotImplementedError, match="oauth_token_exchange"):
        get_subagents(config)


def test_get_subagents_peer_type_is_wrapped_in_agent_tool() -> None:
    config = {
        "buddy": SubagentConfig(
            url=Url("https://agent.example/api"),
            type="peer",
            auth="none",
        )
    }

    result = get_subagents(config)

    assert result.delegate_subagents == []
    assert len(result.peer_subagents) == 1
    tool = result.peer_subagents[0]
    assert isinstance(tool, agent_tool.AgentTool)
    wrapped_agent = _assert_is_remote_agent(tool.agent)
    assert wrapped_agent.name == "buddy"
    assert (
        wrapped_agent._agent_card_source  # pyright: ignore[reportPrivateUsage]
        == "https://agent.example/api/.well-known/agent-card.json"
    )
    assert _get_httpx_client(wrapped_agent) is None
    assert not _has_token_forward_interceptor(wrapped_agent)
    assert wrapped_agent._a2a_client_factory._config.streaming is True  # pyright: ignore[reportPrivateUsage]


def test_get_subagents_routes_each_agent_by_type_preserving_order() -> None:
    config = {
        "delegate_one": SubagentConfig(
            url=Url("https://one.example/api"),
            type="delegate",
            auth="none",
        ),
        "peer_one": SubagentConfig(
            url=Url("https://two.example/api"),
            type="peer",
            auth="none",
        ),
        "delegate_two": SubagentConfig(
            url=Url("https://three.example/api"),
            type="delegate",
            auth="none",
        ),
    }

    result = get_subagents(config)

    assert [_assert_is_remote_agent(a).name for a in result.delegate_subagents] == [
        "delegate_one",
        "delegate_two",
    ]
    assert len(result.peer_subagents) == 1
    assert _assert_is_remote_agent(result.peer_subagents[0].agent).name == "peer_one"


def test_get_subagents_strips_trailing_slash_when_building_agent_card_url() -> None:
    config = {
        "helper": SubagentConfig(
            url=Url("https://agent.example/api/"),
            type="delegate",
            auth="none",
        )
    }

    result = get_subagents(config)

    agent = _assert_is_remote_agent(result.delegate_subagents[0])
    assert (
        agent._agent_card_source  # pyright: ignore[reportPrivateUsage]
        == "https://agent.example/api/.well-known/agent-card.json"
    )
