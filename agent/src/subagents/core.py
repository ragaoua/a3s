from typing import NamedTuple

import httpx
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.a2a.agent.config import A2aRemoteAgentConfig, RequestInterceptor
from google.adk.agents import BaseAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import agent_tool

from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import (
    OAuthClientCredentialsAuthConfig,
    OAuthTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
    OutboundApiKeyAuthConfig,
    SubagentConfig,
)
from src.subagents.interceptors import token_forward_before_request


class GetSubagentResult(NamedTuple):
    delegate_subagents: list[BaseAgent]
    peer_subagents: list[agent_tool.AgentTool]


def get_subagents(config: dict[str, SubagentConfig]) -> GetSubagentResult:
    delegate_subagents: list[BaseAgent] = []
    peer_subagents: list[agent_tool.AgentTool] = []

    for agent_name, agent_config in config.items():
        httpx_client: httpx.AsyncClient | None = None
        remote_agent_config: A2aRemoteAgentConfig | None = None

        if isinstance(agent_config.auth, OutboundApiKeyAuthConfig):
            httpx_client = httpx.AsyncClient(
                headers={"API-Key": agent_config.auth.api_key.get_secret_value()}
            )
        elif isinstance(agent_config.auth, OAuthClientCredentialsAuthConfig):
            httpx_client = httpx.AsyncClient(
                auth=OAuthClientCredentialsAuth(
                    server_url=agent_config.url,
                    server_auth_config=agent_config.auth,
                )
            )
        elif isinstance(agent_config.auth, OAuthTokenForwardAuthConfig):
            remote_agent_config = A2aRemoteAgentConfig(
                request_interceptors=[
                    RequestInterceptor(before_request=token_forward_before_request)
                ]
            )
        elif isinstance(agent_config.auth, OAuthTokenExchangeAuthConfig):
            raise NotImplementedError(
                "agent.subagents[].auth.mode='oauth_token_exchange' is not implemented yet"
            )

        a2a_client_factory = ClientFactory(
            config=ClientConfig(httpx_client=httpx_client, streaming=True)
        )
        remote_agent = RemoteA2aAgent(
            name=agent_name,
            agent_card=f"{str(agent_config.url).rstrip('/')}/{AGENT_CARD_WELL_KNOWN_PATH.lstrip('/')}",
            use_legacy=False,
            a2a_client_factory=a2a_client_factory,
            config=remote_agent_config,
        )
        if agent_config.type == "delegate":
            delegate_subagents.append(remote_agent)
        else:
            peer_subagents.append(agent_tool.AgentTool(remote_agent))

    return GetSubagentResult(
        delegate_subagents=delegate_subagents,
        peer_subagents=peer_subagents,
    )
