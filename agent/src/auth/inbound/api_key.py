from hashlib import sha256
from hmac import compare_digest
from typing import final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.inbound.constants import EXCLUDED_PATHS


def hash_api_key(api_key: str) -> str:
    """Return the lowercase hex SHA-256 digest of an API key.

    The digest scheme must match how the configured `auth.api_key` hash is
    produced (see the README): a plain, unsalted SHA-256 of the UTF-8 key.
    """
    return sha256(api_key.encode("utf-8")).hexdigest()


@final
class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    DEFAULT_HEADER_NAME = "API-Key"

    def __init__(
        self,
        app: ASGIApp,
        # The expected SHA-256 digest of the API key, not the plaintext key:
        # `dispatch` hashes the incoming header and compares digests.
        api_key: str,
        header_name: str = DEFAULT_HEADER_NAME,
    ):
        super().__init__(app)
        self.api_key = api_key
        self.header_name = header_name

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        received_key = request.headers.get(self.header_name)
        if received_key is None or not compare_digest(
            hash_api_key(received_key), self.api_key
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": self.header_name},
            )

        return await call_next(request)
