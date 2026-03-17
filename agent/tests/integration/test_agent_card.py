from pathlib import Path

from a2a.types import APIKeySecurityScheme, In, OAuth2SecurityScheme, SecurityScheme
import httpx
import pytest
from a2a.client import A2AClient

from src.auth import ApiKeyAuthMiddleware
from src.config import APIKeyAuth, Config, OAuth2Auth
from tests.integration.utils import (
    run_single_turn_test,
    start_agent_server,
    wait_for_agent_card,
)

pytest_plugins = ("pytest_asyncio",)


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
    config = Config(
        LLM_API_URI="endpoint",
        LLM_API_KEY="fakekey",
        MODEL="model",
        AGENT_NAME="Cody",
        AGENT_DESCRIPTION="A helpful coding assistant",
        AGENT_INSTRUCTIONS="""
You are a coding agent. Use the tools provided to access the user's requests regarding coding tasks.
DO NOT PRINT OUT CODE TO THE USER unless explicitely prompted. ALWAYS WRITE CODE TO FILES.
Take initiatives regarding file names, architecture etc.""",
        LISTEN_PORT=10000,
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
                assert agent_card.security_schemes is not None
                schemes = agent_card.security_schemes.items()

                security_scheme = agent_card.security_schemes["OAuth2SecurityScheme"]
                assert isinstance(security_scheme.root, OAuth2SecurityScheme)
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
