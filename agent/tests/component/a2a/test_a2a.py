import httpx
import pytest
from a2a.types import (
    Artifact,
    StreamResponse,
    Task,
    TaskState,
    TaskStatus,
)

from tests.common.a2a import (
    A2aServerFixture,
    get_adk_data_parts,
    get_artifact_text_parts,
    get_text_parts,
    send_message,
    send_message_streaming,
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


def _task_from_artifacts(artifacts: list[Artifact]) -> Task:
    """Reassemble a task from streamed artifact-update chunks."""
    return Task(
        status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
        artifacts=artifacts,
    )


def _streamed_artifacts(chunks: list[StreamResponse]) -> list[Artifact]:
    return [
        chunk.artifact_update.artifact
        for chunk in chunks
        if chunk.HasField("artifact_update")
    ]


def _assert_first_streaming_response_chunk(chunk: StreamResponse):
    assert chunk.HasField("task")
    assert chunk.task.status.state == TaskState.TASK_STATE_SUBMITTED


def _assert_working_streaming_response_chunk(chunk: StreamResponse):
    assert chunk.HasField("status_update")
    assert chunk.status_update.status.state == TaskState.TASK_STATE_WORKING


def _assert_penultimate_streaming_response_chunk(chunk: StreamResponse):
    assert chunk.HasField("artifact_update")
    assert chunk.artifact_update.last_chunk


def _assert_last_streaming_response_chunk(chunk: StreamResponse):
    assert chunk.HasField("status_update")
    assert chunk.status_update.status.state == TaskState.TASK_STATE_COMPLETED


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

    task = await send_message(a2a_server.base_url, text="hi")

    assert get_text_parts(task.artifacts[0].parts) == [expected]
    assert len(a2a_server.mock_llm.requests) == 1


@pytest.mark.asyncio
async def test_send_message_streaming_surfaces_llm_reply_in_task(
    a2a_server: A2aServerFixture,
) -> None:
    expected = "Hello back from the mock LLM!"
    a2a_server.mock_llm.stub_response(expected)

    chunks = await send_message_streaming(a2a_server.base_url, text="hi")

    first_chunk, second_chunk, *middle_chunks, penultimate_chunk, last_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    _assert_working_streaming_response_chunk(second_chunk)
    _assert_penultimate_streaming_response_chunk(penultimate_chunk)
    _assert_last_streaming_response_chunk(last_chunk)

    assert len(middle_chunks) == 1
    middle_chunk = middle_chunks[0]
    assert middle_chunk.HasField("artifact_update")
    assert not middle_chunk.artifact_update.last_chunk
    assert get_text_parts(middle_chunk.artifact_update.artifact.parts) == [expected]

    assert len(a2a_server.mock_llm.requests) == 1


@pytest.mark.asyncio
async def test_send_message_exposes_skills_to_llm_and_surfaces_their_contents(
    a2a_server: A2aServerFixture,
) -> None:
    _stub_hello_skill_tool_call(a2a_server.mock_llm)

    task = await send_message(a2a_server.base_url, text="use the hello skill")

    assert "Greetings from Cody!" in get_artifact_text_parts(task)

    _assert_hello_skill_function_calls_and_responses(task)


@pytest.mark.asyncio
async def test_send_message_streaming_exposes_skills_to_llm_and_surfaces_their_contents(
    a2a_server: A2aServerFixture,
) -> None:
    _stub_hello_skill_tool_call(a2a_server.mock_llm)

    chunks = await send_message_streaming(
        a2a_server.base_url, text="use the hello skill"
    )

    first_chunk, second_chunk, *middle_chunks, penultimate_chunk, last_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    _assert_working_streaming_response_chunk(second_chunk)
    _assert_penultimate_streaming_response_chunk(penultimate_chunk)
    _assert_last_streaming_response_chunk(last_chunk)

    task = _task_from_artifacts(_streamed_artifacts(middle_chunks))

    assert "Greetings from Cody!" in get_artifact_text_parts(task)

    _assert_hello_skill_function_calls_and_responses(task)


@pytest.mark.asyncio
async def test_send_message_returns_failed_task_when_llm_call_fails(
    a2a_server: A2aServerFixture,
) -> None:
    a2a_server.mock_llm.stub_error(
        status=500, message="OpenAIException - Connection error."
    )

    task = await send_message(a2a_server.base_url, text="hi")

    assert task.status.state == TaskState.TASK_STATE_FAILED


@pytest.mark.asyncio
async def test_send_message_streaming_returns_failed_task_status_update_when_llm_call_fails(
    a2a_server: A2aServerFixture,
) -> None:
    a2a_server.mock_llm.stub_error(
        status=500, message="OpenAIException - Connection error."
    )

    chunks = await send_message_streaming(a2a_server.base_url, text="hi")

    # The failure path emits a `submitted` task, one or more `working` status
    # updates (ADK reports the LLM error as one of them), then a terminal
    # `failed` update. Only the two ends are contractual — assert on those rather
    # than on an exact chunk count, which ADK is free to grow.
    first_chunk, *working_chunks, last_chunk = chunks

    _assert_first_streaming_response_chunk(first_chunk)
    for chunk in working_chunks:
        _assert_working_streaming_response_chunk(chunk)

    assert last_chunk.HasField("status_update")
    assert last_chunk.status_update.status.state == TaskState.TASK_STATE_FAILED
