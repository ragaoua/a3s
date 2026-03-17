import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
import uvicorn
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    GetTaskRequest,
    GetTaskResponse,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskQueryParams,
)

from src.config import Config

AGENT_DIR = Path(__file__).resolve().parents[2]

pytest_plugins = ("pytest_asyncio",)


async def wait_for_agent_card(base_url: str, httpx_client: httpx.AsyncClient):
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


def start_agent_server(config: Config):
    from src.agent import create_app

    app = create_app(config)
    server_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=config.LISTEN_PORT,
    )
    server = uvicorn.Server(server_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a message."""
    payload: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": uuid4().hex,
        },
    }

    if task_id:
        payload["message"]["taskId"] = task_id

    if context_id:
        payload["message"]["contextId"] = context_id
    return payload


def pretty_print_json(json_str: str) -> None:
    print(json.dumps(json.loads(json_str), indent=4))


def print_json_response(response: Any, description: str) -> None:
    """Helper function to print the JSON representation of a response."""
    print(f"--- {description} ---")
    if hasattr(response, "root"):
        pretty_print_json(response.root.model_dump_json(exclude_none=True))
    else:
        pretty_print_json(response.model_dump(mode="json", exclude_none=True))


async def run_single_turn_test(client: A2AClient) -> None:
    """Runs a single-turn non-streaming test."""

    send_message_payload = create_send_message_payload(
        text="Write a simple python cli to compute a 2-operator math operation"
    )
    request = SendMessageRequest(
        id=str(uuid4()), params=MessageSendParams(**send_message_payload)
    )

    print("--- ✉️  Single Turn Request ---")
    # Send Message
    response: SendMessageResponse = await client.send_message(request)
    print_json_response(response, "📥 Single Turn Request Response")
    if not isinstance(response.root, SendMessageSuccessResponse):
        raise RuntimeError("received non-success response")

    if not isinstance(response.root.result, Task):
        raise RuntimeError("received non-task response")

    task_id: str = response.root.result.id
    print("--- ❔ Query Task ---")
    # query the task
    get_request = GetTaskRequest(id=str(uuid4()), params=TaskQueryParams(id=task_id))
    get_response: GetTaskResponse = await client.get_task(get_request)
    print_json_response(get_response, "📥 Query Task Response")


@pytest.mark.asyncio
async def test_expose_a2a_agent_and_run_test_script() -> None:
    config = Config(
        LLM_API_URI="endpoint",
        LLM_API_KEY="fakekey",
        MODEL="model",
        AGENT_NAME="Cody",
        AGENT_DESCRIPTION="A helpful coding assistant",
        AGENT_INTRUCTIONS="""
You are a coding agent. Use the tools provided to access the user's requests regarding coding tasks.
DO NOT PRINT OUT CODE TO THE USER unless explicitely prompted. ALWAYS WRITE CODE TO FILES.
Take initiatives regarding file names, architecture etc.""",
        LISTEN_PORT=10000,
        NO_AUTH=True,
    )

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = f"http://localhost:{config.LISTEN_PORT}"
            agent_card = await wait_for_agent_card(agent_url, httpx_client)
            print("--- 📇 Resolved agent card ---")
            print(agent_card.model_dump_json(indent=2, exclude_none=True))

            # Create a client to interact with the agent
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card,
            )

            await run_single_turn_test(client)
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

        assert not server_thread.is_alive(), "Agent server thread failed to stop"
