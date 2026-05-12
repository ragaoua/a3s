from typing import final
from returns.result import Failure, Result, Success

from authlib.jose import JsonWebKey, JWTClaims, KeySet, jwt
from authlib.jose.errors import JoseError
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from authlib.oauth2.rfc9068.claims import JWTAccessTokenClaims
from pydantic import JsonValue
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from typing_extensions import override

from src.auth.inbound.constants import EXCLUDED_PATHS
from src.auth.context import (
    bind_current_authorization_header,
)
from src.auth.oauth_client_auth import build_client_authenticated_request
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthDiscoveredJwksPolicyConfig,
)
from src.observability.logging import get_logger
from src.utils import FetchJson, fetch_json

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
        fetch_json: FetchJson = fetch_json,
    ):
        super().__init__(app)
        self.issuer_url = issuer_url.rstrip("/")
        self.realm = realm
        self.config = config
        self._fetch_json = fetch_json

    @staticmethod
    def _validate_authorization_server_metadata(
        metadata_raw: dict[str, JsonValue],
        *,
        expected_issuer: str,
    ) -> Result[AuthorizationServerMetadata, str]:
        try:
            metadata = AuthorizationServerMetadata(metadata_raw)
            metadata.validate_issuer()
        except Exception as err:
            return Failure(f"Failed to validate authorization server metadata: {err}")

        metadata_issuer = str(metadata.get("issuer", "")).rstrip("/")
        if metadata_issuer != expected_issuer:
            return Failure(
                "Failed to validate authorization server metadata: Issuer mismatch in OAuth2 authorization server metadata"
            )

        return Success(metadata)

    async def _fetch_authorization_server_metadata(
        self,
    ) -> Result[AuthorizationServerMetadata, str]:
        try:
            metadata_url = get_well_known_url(self.issuer_url, external=True)
            metadata_raw = await self._fetch_json(metadata_url)
        except Exception as err:
            return Failure(f"Failed to fetch authorization server metadata: {err}")

        return self._validate_authorization_server_metadata(
            metadata_raw,
            expected_issuer=self.issuer_url,
        )

    async def _discover_jwks_uri(
        self,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> Result[str, str]:
        if not metadata:
            res = await self._fetch_authorization_server_metadata()
            if isinstance(res, Failure):
                return res
            metadata = res.unwrap()

        try:
            metadata.validate_jwks_uri()
        except Exception as err:
            return Failure(
                f"Failed to validate authorization server metadata JWKS URI: {err}"
            )

        jwks_uri = metadata.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            return Failure(
                "OAuth2 authorization server metadata does not contain a valid jwks_uri"
            )

        return Success(jwks_uri)

    async def _fetch_jwk_set(
        self,
        *,
        jwt_policy_config: OAuthJwtPolicyConfig,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> Result[KeySet, str]:
        """
        jwt_policy_config is taken as a parameter rather than read from
        self.config.jwt so the caller's null-narrowing flows through and
        is shared with sibling calls (e.g. _validate_jwt) without rechecking.
        """
        if isinstance(jwt_policy_config.jwks, OAuthStaticJwksPolicyConfig):
            jwks_url = str(jwt_policy_config.jwks.url)
        else:
            res = await self._discover_jwks_uri(metadata)
            if isinstance(res, Failure):
                return res
            jwks_url = res.unwrap()

        try:
            jwks_raw = await self._fetch_json(jwks_url)
            jwks = JsonWebKey.import_key_set(jwks_raw)
        except Exception as err:
            return Failure(f"Failed to fetch JWKS from authorization server: {err}")

        return Success(jwks)

    def _requires_authorization_server_metadata(self) -> bool:
        return (
            self.config.jwt is not None
            and isinstance(self.config.jwt.jwks, OAuthDiscoveredJwksPolicyConfig)
        ) or (
            self.config.introspection is not None
            and isinstance(
                self.config.introspection, OAuthDiscoveredIntrospectionPolicyConfig
            )
        )

    async def _discover_introspection_endpoint(
        self,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> Result[str, str]:
        if not metadata:
            res = await self._fetch_authorization_server_metadata()
            if isinstance(res, Failure):
                return res
            metadata = res.unwrap()

        try:
            metadata.validate_introspection_endpoint()
        except Exception as err:
            return Failure(
                f"Failed to validate authorization server metadata introspection endpoint: {err}"
            )

        introspection_endpoint = metadata.get("introspection_endpoint")
        if not isinstance(introspection_endpoint, str) or not introspection_endpoint:
            return Failure(
                "OAuth2 authorization server metadata does not contain a valid introspection_endpoint"
            )

        return Success(introspection_endpoint)

    async def _introspect_access_token(
        self,
        token: str,
        *,
        introspection_config: OAuthStaticIntrospectionPolicyConfig
        | OAuthDiscoveredIntrospectionPolicyConfig,
        metadata: AuthorizationServerMetadata | None = None,
    ) -> Result[None, JSONResponse]:
        """
        introspection_config is taken as a parameter rather than read from
        self.config.introspection so the caller's null-narrowing flows
        through without rechecking.
        """

        if isinstance(introspection_config, OAuthStaticIntrospectionPolicyConfig):
            endpoint = str(introspection_config.endpoint)
        else:
            res = await self._discover_introspection_endpoint(metadata)
            if isinstance(res, Failure):
                return res.alt(
                    lambda err: JSONResponse(
                        status_code=503,
                        content={"detail": res.failure()},
                    )
                )
            endpoint = res.unwrap()

        try:
            introspection_response = await self._fetch_json(
                build_client_authenticated_request(
                    url=endpoint,
                    body={"token": token, "token_type_hint": "access_token"},
                    auth_method=introspection_config.auth_method,
                    client_id=introspection_config.client_id,
                    client_secret=introspection_config.client_secret,
                )
            )
        except Exception as err:
            return Failure(
                JSONResponse(
                    status_code=503,
                    content={
                        "detail": f"Failed to introspect token via '{endpoint}': {err}"
                    },
                )
            )

        active = introspection_response.get("active")

        if active is False:
            return Failure(
                self._unauthorized_error_response(
                    error="invalid_token",
                    error_description="The access token provided is expired, revoked, malformed, or invalid for other reasons.",
                )
            )

        if active is not True:
            return Failure(
                JSONResponse(
                    status_code=503,
                    content={
                        "detail": "OAuth2 token introspection response is missing a valid 'active' flag"
                    },
                )
            )

        return Success(None)

    @staticmethod
    def _get_rfc9068_claims_options(
        *,
        issuer_url: str,
        resource_server: str,
    ) -> dict[str, JsonValue]:
        return {
            "iss": {"essential": True, "value": issuer_url},
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

    @staticmethod
    def _validate_jwt(
        token: str,
        *,
        issuer_url: str,
        jwt_config: OAuthJwtPolicyConfig,
        jwk_set: KeySet,
    ) -> Result[None, str]:
        """
        jwt_config is taken as a parameter rather than read from
        self.config.jwt so the caller's null-narrowing flows through and
        is shared with sibling calls (e.g. _fetch_jwk_set) without rechecking.
        """

        # Base JWT validation always uses JWTClaims so registered NumericDate
        # claims like exp/nbf/iat are validated when the token includes them.
        claims_cls: type[JWTClaims] = JWTClaims
        claims_options: dict[str, JsonValue] = {
            "iss": {"essential": True, "value": issuer_url},
        }

        if jwt_config.rfc9068 is not None:
            claims_cls = JWTAccessTokenClaims
            claims_options = {
                **claims_options,
                **OAuth2BearerAuthMiddleware._get_rfc9068_claims_options(
                    issuer_url=issuer_url,
                    resource_server=jwt_config.rfc9068.resource_server,
                ),
            }

        for key, value in jwt_config.claims.items():
            claims_options = {
                **claims_options,
                key: {"essential": True, "value": value},
            }

        try:
            claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
                token,
                jwk_set,
                claims_cls=claims_cls,
                claims_options=claims_options,
            )
            claims.validate()  # pyright: ignore[reportUnknownMemberType]
        except Exception as err:
            if isinstance(err, JoseError) and err.error == "expired_token":
                return Failure("The access token expired")

            return Failure("The access token is invalid")

        return Success(None)

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

    async def _validate_token(self, token: str) -> Result[None, JSONResponse]:
        auth_server_metadata: AuthorizationServerMetadata | None = None
        if self._requires_authorization_server_metadata():
            res = await self._fetch_authorization_server_metadata()

            if isinstance(res, Failure):
                return Failure(
                    JSONResponse(
                        status_code=503,
                        content={"detail": res.failure()},
                    ),
                )

            auth_server_metadata = res.unwrap()

        if self.config.jwt is not None:
            res = await self._fetch_jwk_set(
                jwt_policy_config=self.config.jwt, metadata=auth_server_metadata
            )

            if isinstance(res, Failure):
                return Failure(
                    JSONResponse(
                        status_code=503,
                        content={"detail": res.failure()},
                    ),
                )

            jwk_set = res.unwrap()

            res = self._validate_jwt(
                token,
                issuer_url=self.issuer_url,
                jwt_config=self.config.jwt,
                jwk_set=jwk_set,
            )

            if isinstance(res, Failure):
                return Failure(
                    self._unauthorized_error_response(
                        error="invalid_token",
                        error_description=res.failure(),
                    )
                )

        if self.config.introspection is not None:
            res = await self._introspect_access_token(
                token,
                introspection_config=self.config.introspection,
                metadata=auth_server_metadata,
            )

            if isinstance(res, Failure):
                return res

        return Success(None)

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

        res = await self._validate_token(token)
        if isinstance(res, Failure):
            return res.failure()

        with bind_current_authorization_header(f"Bearer {token}"):
            return await call_next(request)
