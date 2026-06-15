"""End-to-end tests for the engine's real CLI entrypoint.

Covers: console-script registration, `load_config()` reading YAML from disk,
`${ENV_VAR}` substitution, `setup_logging` / `setup_telemetry`, OAuth2 inbound
middleware under real Keycloak, an LLM round-trip against a real model, and
the stdin `"q"` quit-watcher shutdown path in `src/main.py`.
"""

from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
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

from tests.common.a2a import create_send_message_payload, wait_for_agent_card
from tests.common.containers_utilities import poll_until_ready
from tests.common.keycloak import KeycloakFixture
from tests.e2e.conftest import AgentContainer
from tests.e2e.utils import PROJECT_DIR, make_agent_config

pytestmark = pytest.mark.e2e


def _fetch_bearer_token(keycloak: KeycloakFixture) -> str:
    """Mint a client_credentials access token against Keycloak's token endpoint."""
    response = httpx.post(
        keycloak.token_endpoint_url,
        data={
            "grant_type": "client_credentials",
            "client_id": keycloak.confidential_client_id,
            "client_secret": keycloak.confidential_client_secret,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def _send_and_assert_text(
    *,
    base_url: str,
    prompt: str,
    token: str,
    timeout: float,
):
    """Fetch the agent card, send `prompt` over A2A with the bearer token, and
    assert at least one non-empty text part comes back within `timeout`
    seconds."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=5)
    ) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(timeout, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text=prompt)),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse), (
        f"a2a response was not success: {response.root!r}"
    )
    assert isinstance(response.root.result, Task)
    task = response.root.result
    assert task.artifacts, "task returned no artifacts"

    text_parts = [
        part.root.text
        for artifact in task.artifacts
        for part in artifact.parts
        if part.root.kind == "text" and part.root.text
    ]
    assert text_parts, "no non-empty text parts in a2a response"


@pytest.mark.asyncio
async def test_local_round_trip(
    tmp_path: Path,
    e2e_llm_env: dict[str, str],
    keycloak: KeycloakFixture,
) -> None:
    """Spawn the real `a3s-agent` console script against a real LLM under
    OAuth2 inbound auth, do an A2A round trip, then shut the server down via
    the stdin `"q"` quit path and assert it exits cleanly."""
    listen_address = "127.0.0.1"
    with socket.socket() as s:
        s.bind((listen_address, 0))
        port: int = s.getsockname()[1]

    config_path = make_agent_config(
        path=tmp_path,
        listen_address=listen_address,
        listen_port=port,
        issuer_url=keycloak.internal_issuer_url,
        jwks_url=keycloak.external_jwks_url,
    )
    base_url = f"http://{listen_address}:{port}"

    env = {
        **os.environ,
        **e2e_llm_env,
        "A3S_CONFIG_FILE": str(config_path),
    }

    proc = subprocess.Popen(
        ["uv", "run", "a3s-agent"],
        cwd=str(PROJECT_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        poll_until_ready(
            f"{base_url}/.well-known/agent-card.json",
            timeout_seconds=30.0,
            description="agent card",
        )

        token = _fetch_bearer_token(keycloak)
        await _send_and_assert_text(
            base_url=base_url,
            prompt="say hi",
            token=token,
            timeout=60.0,
        )

        assert proc.stdin is not None
        _ = proc.stdin.write("q\n")
        proc.stdin.flush()
        proc.stdin.close()

        returncode = proc.wait(timeout=10)
        assert returncode == 0, f"agent exited with non-zero status: {returncode}"
    except BaseException as exc:
        # Kill -> drain stdio -> surface it in the failure message so the
        # developer can see why the agent misbehaved without re-running.
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "<timed out reading stdio>", "<timed out reading stdio>"
        raise AssertionError(
            f"local e2e round-trip failed: {exc}\n"
            f"--- agent stdout ---\n{stdout}"
            f"--- agent stderr ---\n{stderr}"
        ) from exc


@pytest.mark.asyncio
async def test_container_round_trip(
    agent_container: AgentContainer,
    keycloak: KeycloakFixture,
) -> None:
    """Drive an A2A round trip against the agent running in its docker
    container. The `agent_container` fixture builds the image, starts the
    container on the e2e network with OAuth2 wired to Keycloak, waits for
    the agent card, and tears the container down at end-of-test."""
    token = _fetch_bearer_token(keycloak)
    try:
        await _send_and_assert_text(
            base_url=agent_container.base_url,
            prompt="say hi",
            token=token,
            timeout=60.0,
        )
    except BaseException as exc:
        stdout, stderr = agent_container.container.get_logs()
        raise AssertionError(
            f"containerised e2e round-trip failed: {exc}\n"
            f"--- agent stdout ---\n"
            f"{stdout.decode('utf-8', errors='replace')}"
            f"--- agent stderr ---\n"
            f"{stderr.decode('utf-8', errors='replace')}"
        ) from exc
