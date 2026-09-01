import httpx
import pytest

from src.auth.inbound import ApiKeyAuthMiddleware
from tests.common.a2a import (
    A2aServerFixture,
    agent_card_rpc_url,
    wait_for_agent_card,
)


@pytest.mark.asyncio
async def test_agent_card_advertises_a_single_jsonrpc_interface(
    agent_with_no_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_no_inbound_auth.base_url, httpx_client
        )

    assert len(agent_card.supported_interfaces) == 1
    interface = agent_card.supported_interfaces[0]
    assert interface.url == agent_with_no_inbound_auth.base_url
    assert interface.protocol_binding == "JSONRPC"
    assert interface.protocol_version == "1.0"


@pytest.mark.asyncio
async def test_agent_card_omits_security_scheme_in_no_auth_mode(
    agent_with_no_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_no_inbound_auth.base_url, httpx_client
        )

    assert agent_card_rpc_url(agent_card) == agent_with_no_inbound_auth.base_url
    assert not agent_card.security_schemes
    assert not agent_card.security_requirements


@pytest.mark.asyncio
async def test_agent_card_exposes_api_key_security_scheme(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_api_key_inbound_auth.base_url, httpx_client
        )

    assert agent_card_rpc_url(agent_card) == agent_with_api_key_inbound_auth.base_url

    security_scheme = agent_card.security_schemes["APIKeySecurityScheme"]
    assert security_scheme.HasField("api_key_security_scheme")
    assert (
        security_scheme.api_key_security_scheme.name
        == ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME
    )
    assert security_scheme.api_key_security_scheme.location == "header"
    assert len(agent_card.security_requirements) == 1
    assert list(agent_card.security_requirements[0].schemes) == [
        "APIKeySecurityScheme"
    ]


@pytest.mark.asyncio
async def test_agent_card_exposes_http_bearer_security_scheme(
    agent_with_fake_oauth2_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_fake_oauth2_inbound_auth.base_url, httpx_client
        )

    assert agent_card_rpc_url(agent_card) == agent_with_fake_oauth2_inbound_auth.base_url

    security_scheme = agent_card.security_schemes["HTTPAuthSecurityScheme"]
    assert security_scheme.HasField("http_auth_security_scheme")
    http_auth_scheme = security_scheme.http_auth_security_scheme
    assert http_auth_scheme.scheme == "Bearer"
    assert http_auth_scheme.bearer_format == "JWT"
    assert http_auth_scheme.description == "OAuth 2.0 access token"
    assert len(agent_card.security_requirements) == 1
    assert list(agent_card.security_requirements[0].schemes) == [
        "HTTPAuthSecurityScheme"
    ]


@pytest.mark.asyncio
async def test_introspection_only_agent_card_omits_jwt_bearer_format(
    agent_with_fake_introspection_oauth2_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_fake_introspection_oauth2_inbound_auth.base_url,
            httpx_client,
        )

    security_scheme = agent_card.security_schemes["HTTPAuthSecurityScheme"]
    assert security_scheme.HasField("http_auth_security_scheme")
    http_auth_scheme = security_scheme.http_auth_security_scheme
    assert http_auth_scheme.scheme == "Bearer"
    assert not http_auth_scheme.bearer_format
    assert len(agent_card.security_requirements) == 1
    assert list(agent_card.security_requirements[0].schemes) == [
        "HTTPAuthSecurityScheme"
    ]


@pytest.mark.asyncio
async def test_combined_oauth_agent_card_advertises_jwt_bearer_format(
    agent_with_fake_combined_oauth2_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_fake_combined_oauth2_inbound_auth.base_url,
            httpx_client,
        )

    security_scheme = agent_card.security_schemes["HTTPAuthSecurityScheme"]
    assert security_scheme.HasField("http_auth_security_scheme")
    http_auth_scheme = security_scheme.http_auth_security_scheme
    assert http_auth_scheme.scheme == "Bearer"
    assert http_auth_scheme.bearer_format == "JWT"
    assert len(agent_card.security_requirements) == 1
    assert list(agent_card.security_requirements[0].schemes) == [
        "HTTPAuthSecurityScheme"
    ]
