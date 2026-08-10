import pytest

from tests.common.a2a import (
    A2aServerFixture,
    get_artifact_text_parts,
    send_message,
)


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_in_no_auth_mode(
    agent_with_no_inbound_auth: A2aServerFixture,
) -> None:
    """No-auth mode: no inbound-auth middleware is wired in, so an a2a
    request without any Authorization header flows straight through to the
    stubbed LLM."""
    agent_with_no_inbound_auth.mock_llm.stub_response("Authorized response.")

    task = await send_message(agent_with_no_inbound_auth.base_url, text="ping")

    assert "Authorized response." in get_artifact_text_parts(task)
