from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import Popen

from testcontainers.core.container import DockerContainer

# tests/e2e/utils.py → agent/. The `agent/` dir is what `uv run` needs as its
# cwd for `test_local_round_trip` to pick up the project's pyproject.toml,
# and is also the docker build context the `agent_image` fixture builds from.
PROJECT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LocalAgent:
    base_url: str
    proc: Popen[str]


@dataclass(frozen=True)
class LocalAgentInContainer:
    """A running e2e agent container with OAuth2 inbound auth wired to the
    suite Keycloak. `base_url` is host-reachable; `container` is exposed so a
    failing test can dump its logs."""

    base_url: str
    container: DockerContainer


def make_agent_config(
    *,
    path: Path,
    listen_address: str,
    listen_port: int,
    issuer_url: str,
    jwks_url: str,
) -> Path:
    """Write a minimal `agent.yaml` referencing the A3S_LLM_* env vars and
    configuring OAuth2 inbound auth. No MCP, no subagents, no skills.
    """
    config_path = path / "agent.yaml"
    config_path.write_text(
        f"""\
llm:
  api_url: ${{A3S_LLM_API_URL}}
  api_key: ${{A3S_LLM_API_KEY}}
  model: ${{A3S_LLM_MODEL}}

agent:
  name: E2EAgent
  description: e2e-test agent
  instructions: |
    You are an e2e-test agent. Respond briefly to the user's message.

server:
  listen_address: {listen_address}
  listen_port: {listen_port}

auth:
  mode: oauth2
  issuer_url: {issuer_url}
  policies:
    jwt:
      jwks:
        discovered: false
        url: {jwks_url}""",
        encoding="utf-8",
    )

    return config_path
