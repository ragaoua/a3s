import httpx
import pytest
from a2a.types import APIKeySecurityScheme, In, OAuth2SecurityScheme
from authlib.oauth2.rfc8414 import get_well_known_url

from src.auth.inbound import ApiKeyAuthMiddleware
from tests.common.a2a import A2aServerFixture, wait_for_agent_card
from tests.integration.inbound_auth.conftest import FAKE_OAUTH2_ISSUER


@pytest.mark.asyncio
async def test_agent_card_omits_security_scheme_in_no_auth_mode(
    agent_with_no_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_no_inbound_auth.base_url, httpx_client
        )

    assert agent_card.url == agent_with_no_inbound_auth.base_url
    assert agent_card.security_schemes is None


@pytest.mark.asyncio
async def test_agent_card_exposes_api_key_security_scheme(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_api_key_inbound_auth.base_url, httpx_client
        )

    assert agent_card.url == agent_with_api_key_inbound_auth.base_url
    assert agent_card.security_schemes is not None

    security_scheme = agent_card.security_schemes["APIKeySecurityScheme"]
    assert isinstance(security_scheme.root, APIKeySecurityScheme)
    assert security_scheme.root.name == ApiKeyAuthMiddleware.HEADER_NAME
    assert security_scheme.root.in_ == In.header


@pytest.mark.asyncio
async def test_agent_card_exposes_oauth2_security_scheme(
    agent_with_fake_oauth2_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_fake_oauth2_inbound_auth.base_url, httpx_client
        )

    assert agent_card.url == agent_with_fake_oauth2_inbound_auth.base_url
    assert agent_card.security_schemes is not None

    security_scheme = agent_card.security_schemes["OAuth2SecurityScheme"]
    assert isinstance(security_scheme.root, OAuth2SecurityScheme)
    assert security_scheme.root.oauth2_metadata_url == get_well_known_url(
        str(FAKE_OAUTH2_ISSUER), external=True
    )
