"""End-to-end tests for the engine's real CLI entrypoint.

Covers: console-script registration, `load_config()` reading YAML from disk,
`${ENV_VAR}` substitution, OAuth2 inbound middleware under real Keycloak, an
LLM round-trip against a real model, and the stdin `"q"` quit-watcher shutdown
path in `src/main.py`.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.common.a2a import get_artifact_text_parts, send_message
from tests.common.keycloak import KeycloakFixture
from tests.e2e.utils import LocalAgent, LocalAgentInContainer

pytestmark = pytest.mark.e2e


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
    task = await send_message(
        base_url,
        text=prompt,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert task.artifacts, "task returned no artifacts"

    assert [text for text in get_artifact_text_parts(task) if text], (
        "no non-empty text parts in a2a response"
    )


@pytest.mark.asyncio
async def test_local_round_trip(
    local_agent: LocalAgent,
    keycloak: KeycloakFixture,
) -> None:
    """Spawn the real `a3s-agent` console script against a real LLM under
    OAuth2 inbound auth, do an A2A round trip, then shut the server down via
    the stdin `"q"` quit path and assert it exits cleanly."""
    try:
        token = keycloak.mint_user_access_token()
        await _send_and_assert_text(
            base_url=local_agent.base_url,
            prompt="say hi",
            token=token,
            timeout=60.0,
        )

        assert local_agent.proc.stdin is not None
        _ = local_agent.proc.stdin.write("q\n")
        local_agent.proc.stdin.flush()
        local_agent.proc.stdin.close()

        returncode = local_agent.proc.wait(timeout=10)
        assert returncode == 0, f"agent exited with non-zero status: {returncode}"
    except BaseException as exc:
        # Kill -> drain stdio -> surface it in the failure message so the
        # developer can see why the agent misbehaved without re-running.
        local_agent.proc.kill()
        try:
            stdout, stderr = local_agent.proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "<timed out reading stdio>", "<timed out reading stdio>"
        raise AssertionError(
            f"local e2e round-trip failed: {exc}\n"
            f"--- agent stdout ---\n{stdout}"
            f"--- agent stderr ---\n{stderr}"
        ) from exc


@pytest.mark.asyncio
async def test_container_round_trip(
    local_agent_in_container: LocalAgentInContainer,
    keycloak: KeycloakFixture,
) -> None:
    """Drive an A2A round trip against the agent running in its docker
    container. The `local_agent_in_container` fixture builds the image, starts the
    container on the e2e network with OAuth2 wired to Keycloak, waits for
    the agent card, and tears the container down at end-of-test."""
    token = keycloak.mint_user_access_token()
    try:
        await _send_and_assert_text(
            base_url=local_agent_in_container.base_url,
            prompt="say hi",
            token=token,
            timeout=60.0,
        )
    except BaseException as exc:
        stdout, stderr = local_agent_in_container.container.get_logs()
        raise AssertionError(
            f"containerised e2e round-trip failed: {exc}\n"
            f"--- agent stdout ---\n"
            f"{stdout.decode('utf-8', errors='replace')}"
            f"--- agent stderr ---\n"
            f"{stderr.decode('utf-8', errors='replace')}"
        ) from exc
