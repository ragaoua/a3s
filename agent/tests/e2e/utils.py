from __future__ import annotations

from pathlib import Path

# tests/e2e/utils.py → agent/. The `agent/` dir is what `uv run` needs as its
# cwd for `test_local_round_trip` to pick up the project's pyproject.toml,
# and is also the docker build context the `agent_image` fixture builds from.
PROJECT_DIR = Path(__file__).resolve().parents[2]


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
