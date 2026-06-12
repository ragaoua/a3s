from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class McpServerFixture:
    url: str
    _received_authorization_headers: list[str] = field(default_factory=list)

    def has_received_authorization_header(self):
        return bool(self._received_authorization_headers)


McpServerFactory = Callable[..., McpServerFixture]
