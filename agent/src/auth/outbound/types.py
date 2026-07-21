from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from pydantic_core import Url


class AccessTokenInfo(NamedTuple):
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class PreparedGrant[KeyT]:
    """
    Everything a grant needs to serve a single request:

    - The key its token is cached under.
    - A callable that runs the grant for a fresh token.
    """

    cache_key: KeyT
    fetch: Callable[[], Awaitable[AccessTokenInfo]]


class AccessTokenCacheKey(NamedTuple):
    token_endpoint: Url
    client_id: str


