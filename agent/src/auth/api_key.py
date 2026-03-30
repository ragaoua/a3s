from hmac import compare_digest
from typing import final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.constants import EXCLUDED_PATHS


@final
class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    HEADER_NAME = "API-Key"

    def __init__(
        self,
        app: ASGIApp,
        api_key: str,
    ):
        super().__init__(app)
        self.api_key = api_key

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        received_key = request.headers.get(self.HEADER_NAME)
        if received_key is None or not compare_digest(received_key, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": self.HEADER_NAME},
            )

        request.state.api_key = received_key
        return await call_next(request)
