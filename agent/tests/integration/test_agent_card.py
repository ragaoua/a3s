from a2a.types import APIKeySecurityScheme, In, OAuth2SecurityScheme
from authlib.oauth2.rfc8414 import get_well_known_url
import httpx
import pytest

from src.auth import ApiKeyAuthMiddleware
from src.config import APIKeyAuth, OAuth2Auth
from tests.integration.utils import (
    start_agent_server,
    wait_for_agent_card,
)
from tests.utils import get_base_test_config_ignoring_env_file_with


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("AGENT_API_KEY", "OAUTH2_ISSUER_URL"),
    [
        (None, None),  # No auth
        ("abcdef", None),  # API Key auth
        (None, "https://issuer.example"),  # OAuth2 auth
    ],
)
async def test_agent_card_contains_proper_security_scheme(
    AGENT_API_KEY: str | None,
    OAUTH2_ISSUER_URL: str | None,
) -> None:
    config = get_base_test_config_ignoring_env_file_with(
        NO_AUTH=AGENT_API_KEY is None and OAUTH2_ISSUER_URL is None,
        AGENT_API_KEY=AGENT_API_KEY,
        OAUTH2_ISSUER_URL=OAUTH2_ISSUER_URL,
    )

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = f"http://localhost:{config.LISTEN_PORT}"
            agent_card = await wait_for_agent_card(agent_url, httpx_client)

            if isinstance(config.AUTH, OAuth2Auth):
                assert OAUTH2_ISSUER_URL is not None
                assert agent_card.security_schemes is not None
                schemes = agent_card.security_schemes.items()

                security_scheme = agent_card.security_schemes["OAuth2SecurityScheme"]
                assert isinstance(security_scheme.root, OAuth2SecurityScheme)

                assert security_scheme.root.oauth2_metadata_url == get_well_known_url(
                    OAUTH2_ISSUER_URL, external=True
                )
            elif isinstance(config.AUTH, APIKeyAuth):
                assert agent_card.security_schemes is not None
                schemes = agent_card.security_schemes.items()

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
