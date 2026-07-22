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


class TokenExchangeCacheKey(NamedTuple):
    token_endpoint: Url
    client_id: str
    # sha256 hex digest of the inbound subject token. Exchanged tokens are
    # derived from the caller's token, so the cache MUST be scoped per subject
    # to avoid handing one caller's exchanged token to another. Hashed rather
    # than stored raw as defense-in-depth against leaking tokens via the key.
    subject_token_hash: str
