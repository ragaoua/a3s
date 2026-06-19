"""Fixtures wiring a fresh agent server against the integration subagent container."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from ipaddress import IPv4Address

import pytest
from pydantic import SecretStr
from pydantic_core import Url

from src.a2a.server import build_a2a_server
from src.config.types import (
    AgentConfig,
    OAuthClientCredentialsAuthConfig,
    ServerConfig,
    SubagentConfig,
)
from tests.common.keycloak import KeycloakFixture
from tests.common.llm import LlmFixture
from tests.common.a2a import A2aServerFixture
from tests.common.config import get_base_test_config
from tests.integration.common.subagent import SubagentServerFixture


PEER_SUBAGENT_NAME = "helper"


@pytest.fixture
def agent_with_client_credentials_peer_subagent(
    mock_llm: LlmFixture,
    keycloak: KeycloakFixture,
    subagent_server: SubagentServerFixture,
) -> Iterator[A2aServerFixture]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    config = get_base_test_config(
        llm=mock_llm.llm_config(),
        agent=AgentConfig(
            name="Cody",
            description="A helpful coding assistant",
            instructions="You are a coding agent.",
            subagents={
                PEER_SUBAGENT_NAME: SubagentConfig(
                    url=Url(subagent_server.url),
                    type="peer",
                    auth=OAuthClientCredentialsAuthConfig(
                        mode="oauth_client_credentials",
                        token_endpoint=Url(keycloak.token_endpoint_url),
                        client_id=keycloak.confidential_client_id,
                        client_secret=SecretStr(keycloak.confidential_client_secret),
                    ),
                ),
            },
        ),
        auth="none",
        server=ServerConfig(
            listen_address=IPv4Address("127.0.0.1"),
            listen_port=port,
        ),
    )

    server = build_a2a_server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        yield A2aServerFixture(
            base_url=f"http://127.0.0.1:{port}",
            mock_llm=mock_llm,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
