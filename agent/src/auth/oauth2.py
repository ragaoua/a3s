import json
from json import JSONDecodeError
from typing import Any, final
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from authlib.jose import JsonWebKey, JWTClaims, KeySet, jwt
from authlib.jose.errors import DecodeError, JoseError
from authlib.oauth2.rfc6750 import InvalidTokenError
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from authlib.oauth2.rfc9068.claims import JWTAccessTokenClaims
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.constants import EXCLUDED_PATHS
from src.config.types import (
    OAuthRfc9068PolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.logging import get_logger

logger = get_logger(__name__)


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
        realm: str,
        config: OAuthPoliciesConfig,
    ):
        super().__init__(app)
        self.issuer_url = issuer_url.rstrip("/")
        self.realm = realm
        self.config = config

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

    def _fetch_jwk_set(self) -> KeySet:
        jwks_url = (
            str(self.config.jwks.url)
            if isinstance(self.config.jwks, OAuthStaticJwksPolicyConfig)
            else self._discover_jwks_uri()
        )
        jwks_raw = self._fetch_json(jwks_url)
        return JsonWebKey.import_key_set(jwks_raw)

    def _get_rfc9068_claims_options(self, resource_server: str):
        return {
            "iss": {"essential": True, "value": self.issuer_url},
            "exp": {"essential": True},
            "aud": {"essential": True, "value": resource_server},
            "sub": {"essential": True},
            "client_id": {"essential": True},
            "iat": {"essential": True},
            "jti": {"essential": True},
            "auth_time": {"essential": False},
            "acr": {"essential": False},
            "amr": {"essential": False},
            "scope": {"essential": False},
            "groups": {"essential": False},
            "roles": {"essential": False},
            "entitlements": {"essential": False},
        }

    def _validate_access_token(self, token: str, jwk_set: KeySet):
        claims_options: dict[str, Any] = {
            "iss": {"essential": True, "value": self.issuer_url},
        }
        claims_cls: type[JWTClaims] | None = None

        if self.config.rfc9068 is not None:
            claims_cls = JWTAccessTokenClaims
            claims_options = {
                **claims_options,
                **self._get_rfc9068_claims_options(self.config.rfc9068.resource_server),
            }

        for key, value in self.config.claims.items():
            claims_options = {
                **claims_options,
                key: {"essential": True, "value": value},
            }

        try:
            claims = jwt.decode(
                token,
                jwk_set,
                claims_cls=claims_cls,
                claims_options=claims_options,
            )
            claims.validate()
        except DecodeError as exc:
            raise InvalidTokenError(realm=self.realm) from exc

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
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            return self._unauthorized_error_response(
                error="invalid_request",
                error_description="Authorization header must use Bearer token",
            )

        try:
            jwk_set = self._fetch_jwk_set()
        except Exception:
            logger.exception("JWKS fetch failed")
            return JSONResponse(
                status_code=503, content={"detail": "Failed to fetch JWKS"}
            )

        try:
            self._validate_access_token(token, jwk_set)
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
