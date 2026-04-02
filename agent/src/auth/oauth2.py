import base64
from typing import Any, Literal, final
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest

from authlib.jose import JsonWebKey, JWTClaims, KeySet, jwt
from authlib.jose.errors import DecodeError, JoseError
from authlib.oauth2.rfc6750 import InvalidTokenError
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from authlib.oauth2.rfc9068.claims import JWTAccessTokenClaims
from pydantic import SecretStr
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.constants import EXCLUDED_PATHS
from src.config.types import (
    OAuthJwtPoliciesConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.logging import get_logger
from src.utils import fetch_json

logger = get_logger(__name__)


class TokenIntrospectionServiceError(RuntimeError):
    pass


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

    def _fetch_authorization_server_metadata(self) -> AuthorizationServerMetadata:
        metadata_url = get_well_known_url(self.issuer_url, external=True)
        metadata_raw = fetch_json(metadata_url)
        metadata = AuthorizationServerMetadata(metadata_raw)
        metadata.validate_issuer()

        metadata_issuer = str(metadata.get("issuer", "")).rstrip("/")
        if metadata_issuer != self.issuer_url:
            raise ValueError("Issuer mismatch in OAuth2 authorization server metadata")

        return metadata

    def _discover_jwks_uri(
        self,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> str:
        metadata = metadata or self._fetch_authorization_server_metadata()
        metadata.validate_jwks_uri()

        jwks_uri = metadata.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError(
                "OAuth2 authorization server metadata does not contain a valid jwks_uri"
            )

        return jwks_uri

    def _discover_introspection_endpoint(
        self,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> str:
        metadata = metadata or self._fetch_authorization_server_metadata()
        metadata.validate_introspection_endpoint()

        introspection_endpoint = metadata.get("introspection_endpoint")
        if not isinstance(introspection_endpoint, str) or not introspection_endpoint:
            raise ValueError(
                "OAuth2 authorization server metadata does not contain a valid "
                "introspection_endpoint"
            )

        return introspection_endpoint

    def _fetch_jwk_set(
        self,
        *,
        jwtPoliciesConfig: OAuthJwtPoliciesConfig,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> KeySet:
        jwks_url = (
            str(jwtPoliciesConfig.jwks.url)
            if isinstance(jwtPoliciesConfig.jwks, OAuthStaticJwksPolicyConfig)
            else self._discover_jwks_uri(metadata)
        )
        jwks_raw = fetch_json(jwks_url)
        return JsonWebKey.import_key_set(jwks_raw)

    def _requires_authorization_server_metadata(self) -> bool:
        return (
            self.config.jwt is not None
            and not isinstance(self.config.jwt.jwks, OAuthStaticJwksPolicyConfig)
        ) or (
            self.config.introspection is not None
            and not isinstance(
                self.config.introspection, OAuthStaticIntrospectionPolicyConfig
            )
        )

    def _get_introspection_request(
        self,
        *,
        token: str,
        endpoint: str,
        auth_method: Literal["client_secret_basic", "client_secret_post"],
        client_id: str,
        client_secret: SecretStr,
    ) -> UrlRequest:
        body = {"token": token, "token_type_hint": "access_token"}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        if auth_method == "client_secret_basic":
            client_credentials = f"{client_id}:{client_secret.get_secret_value()}"
            headers["Authorization"] = "Basic " + base64.b64encode(
                client_credentials.encode("utf-8")
            ).decode("ascii")
        else:
            body["client_id"] = client_id
            body["client_secret"] = client_secret.get_secret_value()

        return UrlRequest(
            endpoint,
            data=urlencode(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    def _introspect_access_token(
        self,
        token: str,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> None:
        if self.config.introspection is None:
            return

        try:
            endpoint = (
                str(self.config.introspection.endpoint)
                if isinstance(
                    self.config.introspection, OAuthStaticIntrospectionPolicyConfig
                )
                else self._discover_introspection_endpoint(metadata)
            )
        except Exception as err:
            raise TokenIntrospectionServiceError(
                "Failed to discover token introspection endpoint"
            ) from err

        introspection_response = fetch_json(
            self._get_introspection_request(
                token=token,
                endpoint=endpoint,
                auth_method=self.config.introspection.auth_method,
                client_id=self.config.introspection.client_id,
                client_secret=self.config.introspection.client_secret,
            ),
            error_cls=TokenIntrospectionServiceError,
            error_message=(f"Failed to introspect token via '{endpoint}'"),
        )
        active = introspection_response.get("active")

        if active is False:
            raise InvalidTokenError(realm=self.realm)

        if active is not True:
            raise TokenIntrospectionServiceError(
                "OAuth2 token introspection response is missing a valid 'active' flag"
            )

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
        jwt_config = self.config.jwt

        if jwt_config is not None and jwt_config.rfc9068 is not None:
            claims_cls = JWTAccessTokenClaims
            claims_options = {
                **claims_options,
                **self._get_rfc9068_claims_options(jwt_config.rfc9068.resource_server),
            }

        for key, value in (jwt_config.claims if jwt_config is not None else {}).items():
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

        auth_server_metadata: AuthorizationServerMetadata | None = None
        if self._requires_authorization_server_metadata():
            try:
                auth_server_metadata = self._fetch_authorization_server_metadata()
            except Exception:
                logger.exception("Authorization server metadata fetch failed")
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Failed to fetch authorization server metadata"},
                )

        jwk_set: KeySet | None = None
        if self.config.jwt is not None:
            try:
                jwk_set = self._fetch_jwk_set(
                    jwtPoliciesConfig=self.config.jwt, metadata=auth_server_metadata
                )
            except Exception:
                logger.exception("JWKS fetch failed")
                return JSONResponse(
                    status_code=503, content={"detail": "Failed to fetch JWKS"}
                )

        try:
            if jwk_set is not None:
                self._validate_access_token(token, jwk_set)
            self._introspect_access_token(token, auth_server_metadata)
        except TokenIntrospectionServiceError:
            logger.exception("Token introspection failed")
            return JSONResponse(
                status_code=503, content={"detail": "Failed to introspect token"}
            )
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
