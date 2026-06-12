from dataclasses import dataclass


@dataclass(frozen=True)
class McpServerFixture:
    url: str
