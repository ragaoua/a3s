"""Fixtures wiring a fresh agent server protected by OAuth2 inbound auth.

The agent runs on the host, but Keycloak's issuer is pinned to the in-network
hostname so its `iss` claim doesn't match anything host-side. We sidestep
discovery (which the middleware derives from `issuer_url`, i.e. the unreachable
internal URL) by configuring static JWKS / introspection URLs that point at
Keycloak's external host port — `issuer_url` stays internal so `iss` validates.
"""

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
    OAuthConfig,
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
    ServerConfig,
)
from src.config.types.auth import OAuthStaticIntrospectionPolicyConfig
from tests.common.a2a import A2aServerFixture
from tests.common.config import get_base_test_config
from tests.common.llm import LlmFixture
from tests.integration.common.keycloak import KeycloakFixture


def _start_agent_server(
    *,
    auth: OAuthConfig,
    mock_llm: LlmFixture,
) -> Iterator[A2aServerFixture]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    config = get_base_test_config(
        llm=mock_llm.llm_config(),
        auth=auth,
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


@pytest.fixture
def agent_with_jwt_inbound_auth(
    mock_llm: LlmFixture,
    keycloak: KeycloakFixture,
) -> Iterator[A2aServerFixture]:
    yield from _start_agent_server(
        mock_llm=mock_llm,
        auth=OAuthConfig(
            mode="oauth2",
            issuer_url=Url(keycloak.internal_issuer_url),
            policies=OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(
                    jwks=OAuthStaticJwksPolicyConfig(
                        url=Url(keycloak.external_jwks_url),
                    ),
                ),
            ),
        ),
    )


@pytest.fixture
def agent_with_introspection_inbound_auth(
    mock_llm: LlmFixture,
    keycloak: KeycloakFixture,
) -> Iterator[A2aServerFixture]:
    yield from _start_agent_server(
        mock_llm=mock_llm,
        auth=OAuthConfig(
            mode="oauth2",
            issuer_url=Url(keycloak.internal_issuer_url),
            policies=OAuthPoliciesConfig(
                introspection=OAuthStaticIntrospectionPolicyConfig(
                    endpoint=Url(keycloak.external_introspection_url),
                    client_id=keycloak.confidential_client_id,
                    client_secret=SecretStr(keycloak.confidential_client_secret),
                ),
            ),
        ),
    )
