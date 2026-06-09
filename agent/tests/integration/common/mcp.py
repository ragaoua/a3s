from dataclasses import dataclass


@dataclass(frozen=True)
class McpServerFixture:
    # URL the agent uses to reach the MCP server (host-side).
    external_url: str
    audience: str
