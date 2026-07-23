import hashlib
from datetime import datetime, timezone
from typing import override

from pydantic_core import Url
from returns.result import Failure

from src.auth.context import get_current_authorization_header
from src.auth.oauth_client_auth import build_client_authenticated_request
from src.auth.oauth_metadata import fetch_authorization_server_metadata
from src.auth.outbound.oauth_grant import OAuthGrantAuth
from src.auth.outbound.types import PreparedGrant
from src.auth.outbound.token_expiry import get_access_token_expiry_date
from src.auth.outbound.types import AccessTokenInfo, TokenExchangeCacheKey
from src.config.types import (
    OAuthStaticTokenExchangeAuthConfig,
    OAuthTokenExchangeAuthConfig,
)


class OAuthTokenExchangeAuth(
    OAuthGrantAuth[TokenExchangeCacheKey, OAuthTokenExchangeAuthConfig]
):
    @override
    async def _prepare_grant(self) -> PreparedGrant[TokenExchangeCacheKey]:
        subject_token = self._get_subject_token()
        token_endpoint = await self._resolve_token_endpoint()

        # Scope the cache per subject: the exchanged token is derived from the
        # caller's token, so two callers must never share a cache entry.
        cache_key = TokenExchangeCacheKey(
            token_endpoint=token_endpoint,
            client_id=self._server_auth_config.client_id,
            subject_token_hash=self._hash_subject_token(subject_token),
        )

        async def fetch() -> AccessTokenInfo:
            return await self._exchange_token(token_endpoint, subject_token)

        return PreparedGrant(cache_key, fetch)

    @staticmethod
    def _hash_subject_token(subject_token: str):
        return hashlib.sha256(subject_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_subject_token() -> str:
        authorization_header = get_current_authorization_header()
        if not authorization_header:
            raise ValueError(
                "Cannot perform OAuth2 token exchange: no inbound Authorization "
                + "header is present to use as the subject token"
            )

        scheme, _, token = authorization_header.partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise ValueError(
                "Cannot perform OAuth2 token exchange: the inbound Authorization "
                + "header must be a Bearer token"
            )

        return token

    async def _resolve_token_endpoint(self) -> Url:
        if isinstance(self._server_auth_config, OAuthStaticTokenExchangeAuthConfig):
            return self._server_auth_config.token_endpoint

        issuer_url = str(self._server_auth_config.issuer_url).rstrip("/")
        return await self._discover_token_endpoint(issuer_url)

    async def _discover_token_endpoint(self, issuer_url: str) -> Url:
        res = await fetch_authorization_server_metadata(
            issuer_url, fetch_json=self._fetch_json
        )
        if isinstance(res, Failure):
            raise ValueError(res.failure())
        metadata = res.unwrap()

        token_endpoint = metadata.get("token_endpoint")
        if not isinstance(token_endpoint, str) or not token_endpoint:
            raise ValueError(
                "Authorization server metadata does not contain a valid token_endpoint"
            )

        return Url(token_endpoint)

    async def _exchange_token(
        self, token_endpoint: Url, subject_token: str
    ) -> AccessTokenInfo:
        request = build_client_authenticated_request(
            url=str(token_endpoint),
            body={
                # RFC 8693 grant type and subject token type. The inbound token is always a
                # validated OAuth2 access token (see the inbound auth middleware), so we always
                # advertise it as `access_token`.
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": subject_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            },
            auth_method=self._server_auth_config.auth_method,
            client_id=self._server_auth_config.client_id,
            client_secret=self._server_auth_config.client_secret,
        )
        token_response = await self._fetch_json(
            request,
            error_message=(
                f"Failed to exchange OAuth2 token for server '{self._server_url}'"
            ),
        )
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or access_token == "":
            raise ValueError(
                "OAuth2 token exchange response is missing a valid 'access_token'"
            )

        return AccessTokenInfo(
            access_token=access_token,
            expires_at=get_access_token_expiry_date(
                token_response,
                access_token,
            ),
        )

    @override
    def _evict_expired_tokens(self) -> None:
        """Drop expired cache entries. Must run synchronously (no await) so the
        snapshot iteration is safe under cooperative scheduling."""
        now = datetime.now(timezone.utc)
        for key, token_info in list(self._access_token_cache.items()):
            if token_info.expires_at is not None and token_info.expires_at <= now:
                _ = self._access_token_cache.pop(key, None)
                lock = self._access_token_cache_locks.get(key)
                if lock is not None and not lock.locked():
                    _ = self._access_token_cache_locks.pop(key, None)
