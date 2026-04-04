from collections.abc import Iterable
from typing import Any

import pytest
from authlib.jose import JsonWebKey, KeySet, jwt
from authlib.jose.errors import InvalidClaimError, MissingClaimError

from src.auth.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredJwksPolicyConfig,
    OAuthRfc9068PolicyConfig,
)


ISSUER_URL = "https://issuer.example"
RESOURCE_SERVER = "api://agent"
_JWK_DICT = {
    "kty": "oct",
    "k": "c2VjcmV0c2VjcmV0c2VjcmV0c2VjcmV0",
    "kid": "test-key-id",
}


def _build_jwk_set() -> KeySet:
    return JsonWebKey.import_key_set({"keys": [_JWK_DICT]})


def _build_middleware(
    *,
    resource_server: str | None = RESOURCE_SERVER,
    claims: dict[str, str] | None = None,
):
    async def app(scope, receive, send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthDiscoveredJwksPolicyConfig(),
                rfc9068=(
                    OAuthRfc9068PolicyConfig(resource_server=resource_server)
                    if resource_server is not None
                    else None
                ),
                claims=claims or {},
            ),
        ),
    )


def _encode_access_token(*, claims: dict[str, Any], typ: str = "at+jwt") -> str:
    key = JsonWebKey.import_key(_JWK_DICT)
    token = jwt.encode({"alg": "HS256", "kid": "test-key-id", "typ": typ}, claims, key)
    return token.decode("utf-8")


def _default_claims(*, audience: str | Iterable[str]) -> dict[str, Any]:
    return {
        "iss": ISSUER_URL,
        "sub": "test-subject",
        "aud": audience,
        "exp": 9999999999,
        "iat": 1700000000,
        "jti": "test-jti",
        "client_id": "test-client-id",
    }


def test_validate_accepts_a_rfc9068_access_token_for_the_configured_audience() -> None:
    token = _encode_access_token(claims=_default_claims(audience=[RESOURCE_SERVER]))
    middleware = _build_middleware()

    middleware._validate_access_token(token, _build_jwk_set())


def test_validate_rejects_a_non_access_token_type() -> None:
    token = _encode_access_token(
        claims=_default_claims(audience=[RESOURCE_SERVER]),
        typ="JWT",
    )
    middleware = _build_middleware()

    with pytest.raises(InvalidClaimError, match="Invalid claim 'typ'"):
        middleware._validate_access_token(token, _build_jwk_set())


def test_validate_ignores_audience_when_resource_server_is_not_configured() -> None:
    token = _encode_access_token(
        claims=_default_claims(
            audience=["api://other"],
        ),
    )
    middleware = _build_middleware(resource_server=None)

    middleware._validate_access_token(token, _build_jwk_set())


@pytest.mark.parametrize(
    "missing_claim",
    ["iss", "sub", "aud", "exp", "iat", "jti", "client_id"],
)
def test_validate_rejects_tokens_missing_required_rfc9068_claims(
    missing_claim: str,
) -> None:
    claims_payload = _default_claims(audience=[RESOURCE_SERVER])
    claims_payload.pop(missing_claim)

    token = _encode_access_token(claims=claims_payload)
    middleware = _build_middleware()

    with pytest.raises(MissingClaimError, match=f"Missing '{missing_claim}' claim"):
        middleware._validate_access_token(token, _build_jwk_set())


def test_validate_uses_custom_claims_to_override_rfc9068_claim_validation() -> None:
    token = _encode_access_token(claims=_default_claims(audience=["api://override"]))
    middleware = _build_middleware(claims={"aud": "api://override"})

    middleware._validate_access_token(token, _build_jwk_set())


def test_validate_custom_claims_use_exact_string_matching() -> None:
    token = _encode_access_token(
        claims={
            **_default_claims(audience=[RESOURCE_SERVER]),
            "scope": "read write",
        }
    )
    middleware = _build_middleware(claims={"scope": "read write"})

    middleware._validate_access_token(token, _build_jwk_set())
