import httpx
import pytest
from authlib.oauth2.rfc8414 import get_well_known_url

from src.auth.inbound import ApiKeyAuthMiddleware
from tests.common.a2a import (
    A2aServerFixture,
    agent_card_rpc_url,
    wait_for_agent_card,
)
from tests.integration.inbound_auth.conftest import FAKE_OAUTH2_ISSUER


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
async def test_agent_card_exposes_oauth2_security_scheme(
    agent_with_fake_oauth2_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_fake_oauth2_inbound_auth.base_url, httpx_client
        )

    assert agent_card_rpc_url(agent_card) == agent_with_fake_oauth2_inbound_auth.base_url

    security_scheme = agent_card.security_schemes["OAuth2SecurityScheme"]
    assert security_scheme.HasField("oauth2_security_scheme")
    assert security_scheme.oauth2_security_scheme.oauth2_metadata_url == (
        get_well_known_url(str(FAKE_OAUTH2_ISSUER), external=True)
    )
    assert len(agent_card.security_requirements) == 1
    assert list(agent_card.security_requirements[0].schemes) == [
        "OAuth2SecurityScheme"
    ]
