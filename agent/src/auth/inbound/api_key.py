from hmac import compare_digest
from typing import final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.inbound.constants import EXCLUDED_PATHS


@final
class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    DEFAULT_HEADER_NAME = "API-Key"

    def __init__(
        self,
        app: ASGIApp,
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
        if received_key is None or not compare_digest(received_key, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": self.header_name},
            )

        return await call_next(request)
