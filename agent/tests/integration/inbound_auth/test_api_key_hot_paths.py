import pytest

from src.auth.inbound import ApiKeyAuthMiddleware
from tests.common.a2a import (
    A2aServerFixture,
    get_artifact_text_parts,
    post_rpc,
    send_message,
)
from tests.integration.inbound_auth.conftest import API_KEY


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_with_valid_api_key(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    """Happy path: a request carrying the configured API key in the
    `API-Key` header passes the middleware and the a2a request flows through
    to the stubbed LLM."""
    agent_with_api_key_inbound_auth.mock_llm.stub_response("Authorized response.")

    task = await send_message(
        agent_with_api_key_inbound_auth.base_url,
        text="ping",
        headers={ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME: API_KEY},
    )

    assert "Authorized response." in get_artifact_text_parts(task)


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_invalid_api_key(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    response = await post_rpc(
        agent_with_api_key_inbound_auth.base_url,
        headers={ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME: "wrong-key"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_without_api_key_header(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    response = await post_rpc(agent_with_api_key_inbound_auth.base_url)

    assert response.status_code == 401
