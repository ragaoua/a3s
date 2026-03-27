import json
from json import JSONDecodeError
from typing import Any, final
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from authlib.jose import JWTClaims, JsonWebKey, KeySet
from authlib.jose.errors import JoseError
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from authlib.oauth2.rfc9068 import JWTBearerTokenValidator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.constants import EXCLUDED_PATHS
from src.loggingManager import LoggingManager

logger = LoggingManager().get_logger(__name__)


class RFC9068AccessTokenValidator(JWTBearerTokenValidator):
    def __init__(self, *, issuer: str, resource_server: str | None, jwk_set: KeySet):
        super().__init__(
            issuer=issuer,
            resource_server=resource_server,
        )
        self._jwk_set = jwk_set

    @override
    def get_jwks(self):
        return self._jwk_set


@final
class OAuth2BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Notes: this is a VERY basic auth middleware that's missing many things
    to be considered prod ready, including (but not limited to):
    - Caching the jwks (When token validation fails, re-fetch the jwks and try once more)
    - Support for OIDC in addition to plain oauth2 for jwks discovery
        (use authlib.oidc.discovery.get_well_known_url)
    - Proper handling of token validation errors
    """

    def __init__(
        self,
        app: ASGIApp,
        issuer_url: str,
        jwks_url: str | None,
        realm: str,
        audience: str | None,
    ):
        super().__init__(app)
        self.issuer_url = issuer_url.rstrip("/")
        self.jwks_url = jwks_url
        self.realm = realm
        self.audience = audience

    def _fetch_json(self, url: str) -> dict[str, Any]:
        try:
            with urlopen(url, timeout=5) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, JSONDecodeError) as err:
            raise ValueError(f"Failed to fetch JSON from '{url}'") from err

    def _discover_jwks_uri(self) -> str:
        metadata_url = get_well_known_url(self.issuer_url, external=True)
        metadata_raw = self._fetch_json(metadata_url)
        metadata = AuthorizationServerMetadata(metadata_raw)
        metadata.validate_issuer()
        metadata.validate_jwks_uri()

        metadata_issuer = str(metadata.get("issuer", "")).rstrip("/")
        if metadata_issuer != self.issuer_url:
            raise ValueError("Issuer mismatch in OAuth2 authorization server metadata")

        jwks_uri = metadata.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError(
                "OAuth2 authorization server metadata does not contain a valid jwks_uri"
            )

        return jwks_uri

    def _fetch_jwk_set(self, jwks_url: str) -> KeySet:
        jwks_raw = self._fetch_json(jwks_url)
        return JsonWebKey.import_key_set(jwks_raw)

    def _get_validated_access_token_claims(
        self, token: str, jwk_set: KeySet
    ) -> JWTClaims:
        validator = RFC9068AccessTokenValidator(
            issuer=self.issuer_url,
            resource_server=self.audience,
            jwk_set=jwk_set,
        )
        claims = validator.authenticate_token(token)
        claims.validate()

        return claims

    def _unauthorized_error_response(
        self,
        error: str | None = None,
        error_description: str | None = None,
    ) -> JSONResponse:
        authenticate_header = f'Bearer realm="{self.realm}"'

        if error:
            authenticate_header += f', error="{error}"'

        if error_description:
            authenticate_header += f', error_description="{error_description}"'

        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": authenticate_header},
        )

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return self._unauthorized_error_response()

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return self._unauthorized_error_response(
                error="invalid_request",
                error_description="Authorization header must use Bearer token",
            )

        token = token.strip()

        jwks_url = self.jwks_url or self._discover_jwks_uri()
        jwk_set = self._fetch_jwk_set(jwks_url)

        try:
            token_payload = self._get_validated_access_token_claims(token, jwk_set)
            request.state.token_claims = dict(token_payload)
            request.state.authorization_header = f"Bearer {token}"
        except Exception as err:
            logger.error("Token validation failed: %s", err)
            if isinstance(err, JoseError) and err.error == "expired_token":
                return self._unauthorized_error_response(
                    error="invalid_token",
                    error_description="The access token expired",
                )
            return self._unauthorized_error_response(
                error="invalid_token",
                error_description="The access token is invalid",
            )

        return await call_next(request)
