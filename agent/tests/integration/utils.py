import asyncio
import json
import threading
import time
from typing import Any
from uuid import uuid4

import httpx
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
        host=str(config.server.listen_address),
        port=config.server.listen_port,
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
