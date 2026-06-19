from uuid import uuid4

import httpx
import pytest
from a2a.client import A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

from tests.common.a2a import (
    A2aServerFixture,
    create_send_message_payload,
    get_adk_data_parts,
    wait_for_agent_card,
)
from tests.common.llm import LlmFixture


def _stub_hello_skill_tool_call(llm: LlmFixture):
    llm.stub_tool_call(name="list_skills", arguments={}, call_id="call_list")
    llm.stub_tool_call(
        name="load_skill",
        arguments={"skill_name": "hello-skill"},
        call_id="call_load",
    )
    llm.stub_response("Greetings from Cody!")


def _assert_hello_skill_function_calls_and_responses(task: Task) -> None:
    function_calls = get_adk_data_parts(task, "function_call")
    function_responses = get_adk_data_parts(task, "function_response")

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


def _assert_first_streaming_response_chunk(chunk: SendStreamingMessageResponse):
    assert isinstance(chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(chunk.root.result, Task)
    assert chunk.root.result.status.state == TaskState.submitted


def _assert_second_streaming_response_chunk(chunk: SendStreamingMessageResponse):
    assert isinstance(chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(chunk.root.result, TaskStatusUpdateEvent)
    assert chunk.root.result.status.state == TaskState.working


def _assert_penultimate_streaming_response_chunk(chunk: SendStreamingMessageResponse):
    assert isinstance(chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(chunk.root.result, TaskArtifactUpdateEvent)
    assert chunk.root.result.last_chunk


def _assert_last_streaming_response_chunk(chunk: SendStreamingMessageResponse):
    assert isinstance(chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(chunk.root.result, TaskStatusUpdateEvent)
    assert chunk.root.result.status.state == TaskState.completed
    assert chunk.root.result.final


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
async def test_send_message_streaming_surfaces_llm_reply_in_task(
    a2a_server: A2aServerFixture,
) -> None:
    expected = "Hello back from the mock LLM!"
    a2a_server.mock_llm.stub_response(expected)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="hi")),
        )

        chunks = [c async for c in client.send_message_streaming(request)]

    first_chunk, second_chunk, *middle_chunks, penultimate_chunk, last_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    _assert_second_streaming_response_chunk(second_chunk)
    _assert_penultimate_streaming_response_chunk(penultimate_chunk)
    _assert_last_streaming_response_chunk(last_chunk)

    assert len(middle_chunks) == 1
    middle_chunk = middle_chunks[0]
    assert isinstance(middle_chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(middle_chunk.root.result, TaskArtifactUpdateEvent)
    assert not middle_chunk.root.result.last_chunk
    assert middle_chunk.root.result.artifact.parts[0].root.kind == "text"
    assert middle_chunk.root.result.artifact.parts[0].root.text == expected

    assert len(a2a_server.mock_llm.requests) == 1


@pytest.mark.asyncio
async def test_send_message_exposes_skills_to_llm_and_surfaces_their_contents(
    a2a_server: A2aServerFixture,
) -> None:
    _stub_hello_skill_tool_call(a2a_server.mock_llm)

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

    _assert_hello_skill_function_calls_and_responses(fetched)


@pytest.mark.asyncio
async def test_send_message_streaming_exposes_skills_to_llm_and_surfaces_their_contents(
    a2a_server: A2aServerFixture,
) -> None:
    _stub_hello_skill_tool_call(a2a_server.mock_llm)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                **create_send_message_payload(text="use the hello skill")
            ),
        )

        chunks = [c async for c in client.send_message_streaming(request)]

    first_chunk, second_chunk, *middle_chunks, penultimate_chunk, last_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    _assert_second_streaming_response_chunk(second_chunk)
    _assert_penultimate_streaming_response_chunk(penultimate_chunk)
    _assert_last_streaming_response_chunk(last_chunk)

    artifacts = [
        chunk.root.result.artifact
        for chunk in middle_chunks
        if isinstance(chunk.root, SendStreamingMessageSuccessResponse)
        and isinstance(chunk.root.result, TaskArtifactUpdateEvent)
    ]
    task = Task(
        id=str(uuid4()),
        context_id=str(uuid4()),
        status=TaskStatus(state=TaskState.completed),
        artifacts=artifacts,
    )

    text_parts = [
        part.root.text
        for artifact in (task.artifacts or [])
        for part in artifact.parts
        if part.root.kind == "text"
    ]
    assert "Greetings from Cody!" in text_parts

    _assert_hello_skill_function_calls_and_responses(task)


@pytest.mark.asyncio
async def test_send_message_returns_failed_task_when_llm_call_fails(
    a2a_server: A2aServerFixture,
) -> None:
    a2a_server.mock_llm.stub_error(
        status=500, message="OpenAIException - Connection error."
    )

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
    assert task.status.state == TaskState.failed


@pytest.mark.asyncio
async def test_send_message_streaming_returns_failed_task_status_update_when_llm_call_fails(
    a2a_server: A2aServerFixture,
) -> None:
    a2a_server.mock_llm.stub_error(
        status=500, message="OpenAIException - Connection error."
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(a2a_server.base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="hi")),
        )

        chunks = [c async for c in client.send_message_streaming(request)]

    assert len(chunks) == 3
    first_chunk, second_chunk, third_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    _assert_second_streaming_response_chunk(second_chunk)

    assert isinstance(third_chunk.root, SendStreamingMessageSuccessResponse)
    assert isinstance(third_chunk.root.result, TaskStatusUpdateEvent)
    assert third_chunk.root.result.status.state == TaskState.failed
