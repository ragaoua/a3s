from typing import override

from pydantic_core import Url

from src.auth.oauth_client_auth import build_client_authenticated_request
from src.auth.outbound.oauth_grant import OAuthGrantAuth
from src.auth.outbound.types import PreparedGrant
from src.auth.outbound.token_expiry import get_access_token_expiry_date
from src.auth.outbound.types import AccessTokenCacheKey, AccessTokenInfo
from src.config.types import OAuthClientCredentialsAuthConfig
from src.utils import FetchJson, fetch_json


class OAuthClientCredentialsAuth(
    OAuthGrantAuth[AccessTokenCacheKey, OAuthClientCredentialsAuthConfig]
):
    def __init__(
        self,
        server_url: Url,
        server_auth_config: OAuthClientCredentialsAuthConfig,
        *,
        fetch_json: FetchJson = fetch_json,
    ):
        super().__init__(server_url, server_auth_config, fetch_json=fetch_json)
        # The token endpoint and client id are fixed for this grant, so the cache
        # key is stable across requests.
        self._cache_key: AccessTokenCacheKey = AccessTokenCacheKey(
            server_auth_config.token_endpoint,
            server_auth_config.client_id,
        )

    @override
    async def _prepare_grant(self) -> PreparedGrant[AccessTokenCacheKey]:
        return PreparedGrant(self._cache_key, self._request_token)

    async def _request_token(self) -> AccessTokenInfo:
        request = build_client_authenticated_request(
            url=str(self._server_auth_config.token_endpoint),
            body={"grant_type": "client_credentials"},
            auth_method=self._server_auth_config.auth_method,
            client_id=self._server_auth_config.client_id,
            client_secret=self._server_auth_config.client_secret,
        )
        token_response = await self._fetch_json(
            request,
            error_message=(
                f"Failed to fetch OAuth2 access token for server '{self._server_url}'"
            ),
        )
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or access_token == "":
            raise ValueError(
                "OAuth2 client credentials response is missing a valid 'access_token'"
            )

        return AccessTokenInfo(
            access_token=access_token,
            expires_at=get_access_token_expiry_date(
                token_response,
                access_token,
            ),
        )
