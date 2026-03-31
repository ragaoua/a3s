from typing import Literal

import httpx
import pytest
from a2a.types import APIKeySecurityScheme, In, OAuth2SecurityScheme
from authlib.oauth2.rfc8414 import get_well_known_url
from pydantic import SecretStr
from pydantic_core import Url

from src.auth import ApiKeyAuthMiddleware
from src.config.types import (
    ApiKeyAuthConfig,
    OAuthConfig,
    OAuthJwtPoliciesConfig,
    OAuthPoliciesConfig,
    OAuthDiscoveredJwksPolicyConfig,
)
from tests.integration.utils import (
    start_agent_server,
    wait_for_agent_card,
)
from tests.utils import get_base_test_config


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth"),
    [
        "none",
        ApiKeyAuthConfig(api_key=SecretStr("abcdef")),  # API Key auth
        OAuthConfig(
            issuer_url=Url("https://issuer.example"),
            policies=OAuthPoliciesConfig(
                jwt=OAuthJwtPoliciesConfig(
                    jwks=OAuthDiscoveredJwksPolicyConfig(discovered=True)
                )
            ),
        ),  # OAuth2 auth
    ],
)
async def test_agent_card_contains_proper_security_scheme(
    auth: OAuthConfig | ApiKeyAuthConfig | Literal["none"],
) -> None:
    config = get_base_test_config(auth=auth)

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = (
                f"http://{config.server.listen_address}:{config.server.listen_port}"
            )
            agent_card = await wait_for_agent_card(agent_url, httpx_client)
            assert agent_card.url == agent_url

            if isinstance(config.auth, OAuthConfig):
                assert config.auth.issuer_url is not None
                assert agent_card.security_schemes is not None

                security_scheme = agent_card.security_schemes["OAuth2SecurityScheme"]
                assert isinstance(security_scheme.root, OAuth2SecurityScheme)

                assert security_scheme.root.oauth2_metadata_url == get_well_known_url(
                    str(config.auth.issuer_url), external=True
                )
            elif isinstance(config.auth, ApiKeyAuthConfig):
                assert agent_card.security_schemes is not None

                security_scheme = agent_card.security_schemes["APIKeySecurityScheme"]
                assert isinstance(security_scheme.root, APIKeySecurityScheme)
                assert security_scheme.root.name == ApiKeyAuthMiddleware.HEADER_NAME
                assert security_scheme.root.in_ == In.header
            else:
                assert agent_card.security_schemes is None

            print(agent_card.model_dump_json(indent=2, exclude_none=True))
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

        assert not server_thread.is_alive(), "Agent server thread failed to stop"
