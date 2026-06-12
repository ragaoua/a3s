from dataclasses import dataclass


@dataclass(frozen=True)
class SubagentServerFixture:
    url: str
