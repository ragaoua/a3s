from dataclasses import dataclass


@dataclass(frozen=True)
class SessionServiceDbFixture:
    connect_string: str
