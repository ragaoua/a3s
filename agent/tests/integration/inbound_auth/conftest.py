"""Fixtures wiring a fresh agent server protected by inbound auth.

For the OAuth2 modes: the agent runs on the host, but Keycloak's issuer is
pinned to the in-network hostname so its `iss` claim doesn't match anything
host-side. We sidestep discovery (which the middleware derives from
`issuer_url`, i.e. the unreachable internal URL) by configuring static JWKS /
introspection URLs that point at Keycloak's external host port — `issuer_url`
stays internal so `iss` validates.

The no-auth, API-key, and fake-OAuth2 fixtures don't need Keycloak — they
exercise the agent's inbound-auth wiring for modes where no real token is
verified end-to-end against an issuer.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from ipaddress import IPv4Address
from typing import Literal

import pytest
from pydantic import SecretStr
from pydantic_core import Url

from src.a2a.server import build_a2a_server
from src.config.types import (
    ApiKeyAuthConfig,
    OAuthConfig,
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
    ServerConfig,
)
from src.config.types.auth import OAuthDiscoveredJwksPolicyConfig
from tests.common.a2a import A2aServerFixture
from tests.common.config import get_base_test_config
from tests.common.llm import LlmFixture
from tests.integration.common.keycloak import KeycloakFixture


# The API key value used by `agent_with_api_key_inbound_auth`. Tests import
# this so they can present the right header instead of duplicating the literal.
API_KEY = "test-api-key"

# Fake issuer URL used by `agent_with_fake_oauth2_inbound_auth`. The agent-card
# surface only requires that the configured issuer flows through to the card;
# no real token is verified, so we don't pay for a Keycloak round trip here.
FAKE_OAUTH2_ISSUER = Url("https://issuer.example")


def _start_agent_server(
    *,
    auth: OAuthConfig | ApiKeyAuthConfig | Literal["none"],
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
def agent_with_no_inbound_auth(
    mock_llm: LlmFixture,
) -> Iterator[A2aServerFixture]:
    yield from _start_agent_server(mock_llm=mock_llm, auth="none")


@pytest.fixture
def agent_with_api_key_inbound_auth(
    mock_llm: LlmFixture,
) -> Iterator[A2aServerFixture]:
    yield from _start_agent_server(
        mock_llm=mock_llm,
        auth=ApiKeyAuthConfig(mode="api_key", api_key=SecretStr(API_KEY)),
    )


@pytest.fixture
def agent_with_fake_oauth2_inbound_auth(
    mock_llm: LlmFixture,
) -> Iterator[A2aServerFixture]:
    """OAuth2-configured agent without a real authorization server.

    Use this for tests that only assert on config-driven surfaces (agent-card
    security scheme, discovery URL, etc.) and don't actually verify a token.
    For end-to-end OAuth2 verification, use `agent_with_jwt_inbound_auth` or
    `agent_with_introspection_inbound_auth`.
    """
    yield from _start_agent_server(
        mock_llm=mock_llm,
        auth=OAuthConfig(
            mode="oauth2",
            issuer_url=FAKE_OAUTH2_ISSUER,
            policies=OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(
                    jwks=OAuthDiscoveredJwksPolicyConfig(discovered=True)
                )
            ),
        ),
    )


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
