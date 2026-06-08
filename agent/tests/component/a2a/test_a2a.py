from typing import Any
from uuid import uuid4

import httpx
import pytest
from a2a.client import A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)

from tests.common.a2a import A2aServerFixture
from tests.integration.utils import create_send_message_payload, wait_for_agent_card


def _adk_data_parts(task: Task, adk_type: str) -> list[dict[str, Any]]:
    return [
        part.root.data  # pyright: ignore[reportUnknownMemberType]
        for artifact in (task.artifacts or [])
        for part in artifact.parts
        if part.root.kind == "data"
        and part.root.metadata is not None
        and part.root.metadata.get("adk_type") == adk_type
    ]


@pytest.mark.asyncio
async def test_agent_card_is_served(a2a_server: A2aServerFixture) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5)) as client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, client)

    assert agent_card.name == "Cody"
    assert agent_card.description == "A helpful coding assistant"


@pytest.mark.asyncio
async def test_send_message_surfaces_llm_reply_in_task(
    a2a_server: A2aServerFixture,
) -> None:
    expected = "Hello back from the mock LLM!"
    a2a_server.mock_llm.stub_response(expected)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="hi")),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    task = response.root.result
    assert task.artifacts is not None
    assert task.artifacts[0].parts[0].root.kind == "text"
    assert task.artifacts[0].parts[0].root.text == expected
    assert len(a2a_server.mock_llm.requests) == 1


@pytest.mark.asyncio
async def test_send_message_exposes_skills_to_llm_and_surfaces_their_contents(
    a2a_server: A2aServerFixture,
) -> None:
    a2a_server.mock_llm.stub_tool_call(
        name="list_skills", arguments={}, call_id="call_list"
    )
    a2a_server.mock_llm.stub_tool_call(
        name="load_skill",
        arguments={"skill_name": "hello-skill"},
        call_id="call_load",
    )
    a2a_server.mock_llm.stub_response("Greetings from Cody!")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                **create_send_message_payload(text="use the hello skill")
            ),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    fetched = response.root.result
    assert fetched.artifacts is not None
    text_parts = [
        part.root.text
        for artifact in fetched.artifacts
        for part in artifact.parts
        if part.root.kind == "text"
    ]
    assert "Greetings from Cody!" in text_parts

    function_calls = _adk_data_parts(fetched, "function_call")
    function_responses = _adk_data_parts(fetched, "function_response")

    list_skills_call = next(c for c in function_calls if c["name"] == "list_skills")
    assert list_skills_call["args"] == {}

    load_skill_call = next(c for c in function_calls if c["name"] == "load_skill")
    assert load_skill_call["args"] == {"skill_name": "hello-skill"}

    list_skills_response = next(
        r for r in function_responses if r["name"] == "list_skills"
    )["response"]
    assert "hello-skill" in list_skills_response["result"]
    assert "says hello in a friendly tone" in list_skills_response["result"]

    load_skill_response = next(
        r for r in function_responses if r["name"] == "load_skill"
    )["response"]
    assert load_skill_response["skill_name"] == "hello-skill"
    assert (
        load_skill_response["instructions"]
        == "Greet the user warmly and ask how their day is going."
    )


# TODO: test send_message_streaming too, not just send_message
