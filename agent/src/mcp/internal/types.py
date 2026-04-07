from datetime import datetime
from typing import NamedTuple
from pydantic_core import Url


class AccessTokenCacheKey(NamedTuple):
    token_endpoint: Url
    client_id: str


class AccessTokenInfo(NamedTuple):
    access_token: str
    expires_at: datetime | None
