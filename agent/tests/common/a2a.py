import asyncio
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import (
    AgentCard,
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageRequest,
    StreamResponse,
    Task,
)
from google.protobuf.json_format import MessageToDict

from tests.common.llm import LlmFixture

DEFAULT_TIMEOUT = httpx.Timeout(30, connect=5)


@dataclass(frozen=True)
class A2aServerFixture:
    base_url: str
    mock_llm: LlmFixture


def new_user_message(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> Message:
    """Build the user `Message` for a send-message call."""
    message = new_text_message(text, role=Role.ROLE_USER)
    message.message_id = uuid4().hex
    if task_id:
        message.task_id = task_id
    if context_id:
        message.context_id = context_id
    return message


async def wait_for_agent_card(
    base_url: str, httpx_client: httpx.AsyncClient
) -> AgentCard:
    STARTUP_TIMEOUT_SECONDS = 10
    RETRY_DELAY_SECONDS = 1
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None

    resolver = A2ACardResolver(httpx_client, base_url)
    while time.monotonic() < deadline:
        try:
            agent_card = await resolver.get_agent_card()
            return agent_card
        except Exception as exc:  # pragma: no cover - exercised on startup delay
            last_error = exc
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    raise TimeoutError(
        f"Agent card not available at {base_url} after {STARTUP_TIMEOUT_SECONDS}s"
    ) from last_error


def agent_card_rpc_url(agent_card: AgentCard) -> str:
    """The RPC URL the card advertises for its first transport binding."""
    return agent_card.supported_interfaces[0].url


def _httpx_client(
    headers: dict[str, str] | None, timeout: float | None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(timeout, connect=5) if timeout else DEFAULT_TIMEOUT,
    )


async def send_message(
    base_url: str,
    *,
    text: str,
    task_id: str | None = None,
    context_id: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Task:
    """Send one message and return the resulting `Task`.

    Uses the non-streaming client so the agent's whole run collapses into a
    single `StreamResponse` carrying the final task.
    """
    async with _httpx_client(headers, timeout) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        client = await create_client(
            agent_card,
            client_config=ClientConfig(httpx_client=httpx_client, streaming=False),
        )
        request = SendMessageRequest(
            message=new_user_message(text, task_id=task_id, context_id=context_id)
        )
        chunks = [chunk async for chunk in client.send_message(request)]

    assert len(chunks) == 1, f"expected a single non-streaming chunk, got {len(chunks)}"
    assert chunks[0].HasField("task"), f"expected a task, got {chunks[0]}"
    return chunks[0].task


async def send_message_streaming(
    base_url: str,
    *,
    text: str,
    task_id: str | None = None,
    context_id: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> list[StreamResponse]:
    """Send one message over the streaming transport and collect every chunk."""
    async with _httpx_client(headers, timeout) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        client = await create_client(
            agent_card,
            client_config=ClientConfig(httpx_client=httpx_client, streaming=True),
        )
        request = SendMessageRequest(
            message=new_user_message(text, task_id=task_id, context_id=context_id)
        )
        return [chunk async for chunk in client.send_message(request)]


async def get_task(
    base_url: str,
    task_id: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Task:
    """Fetch a task by id."""
    async with _httpx_client(headers, timeout) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        client = await create_client(
            agent_card,
            client_config=ClientConfig(httpx_client=httpx_client, streaming=False),
        )
        return await client.get_task(GetTaskRequest(id=task_id))


async def post_rpc(
    base_url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    """POST to the agent's RPC endpoint and return the raw HTTP response.

    For asserting on inbound-auth rejections: the auth middleware answers before
    the request ever reaches an A2A route, so the body is irrelevant and the
    interesting result is an HTTP status rather than a protocol-level reply.
    Going through the A2A client instead would only surface the status as text
    inside an `A2AClientError` message.
    """
    async with _httpx_client(headers, timeout) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        return await httpx_client.post(agent_card_rpc_url(agent_card), json={})


def get_text_parts(parts: list[Part]) -> list[str]:
    return [part.text for part in parts if part.HasField("text")]


def get_artifact_text_parts(task: Task) -> list[str]:
    """Every text part across every artifact on the task, in order."""
    return [
        text for artifact in task.artifacts for text in get_text_parts(artifact.parts)
    ]


def get_adk_data_parts(task: Task, adk_type: str) -> list[dict[str, Any]]:
    """ADK tags the data parts it round-trips through A2A with an `adk_type`."""
    return [
        MessageToDict(part.data)
        for artifact in task.artifacts
        for part in artifact.parts
        if part.HasField("data")
        and "adk_type" in part.metadata
        and part.metadata["adk_type"] == adk_type
    ]
