import time
import uuid
from dataclasses import dataclass

from pydantic import JsonValue
from authlib.jose import jwt
from canaille.core.models import User  # pyright: ignore[reportMissingTypeStubs]
from canaille.oidc.basemodels import Client  # pyright: ignore[reportMissingTypeStubs]
from pytest_iam import Server  # pyright: ignore[reportMissingTypeStubs]

SHORT_LIVED_TOKEN_LIFESPAN_SECONDS = 1


@dataclass(frozen=True)
class IamFixture:
    base_url: str
    issuer_url: str
    jwks_url: str
    confidential_client_id: str
    confidential_client_secret: str
    _server: Server
    _client: Client
    _user: User
    _jwk: dict[str, JsonValue]

    def mint_access_token(
        self,
        *,
        lifetime_seconds: int = 3600,
    ) -> str:
        now = int(time.time())
        header = {"alg": "RS256", "kid": self._jwk["kid"]}
        payload = {
            "iss": self.issuer_url,
            "sub": self._user.user_name,
            "aud": self.confidential_client_id,
            "exp": now + lifetime_seconds,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "client_id": self.confidential_client_id,
            "scope": "openid",
        }
        encoded = jwt.encode(header, payload, self._jwk)  # pyright: ignore[reportUnknownMemberType]
        token_str = encoded.decode("ascii")

        # Persist the token so the introspection endpoint recognises it.
        with self._server.app.app_context():
            _ = self._server.random_token(  # pyright: ignore[reportUnknownMemberType]
                subject=self._user,
                client=self._client,
                access_token=token_str,
                lifetime=lifetime_seconds,
            )

        return token_str

    def mint_short_lived_access_token(self) -> str:
        return self.mint_access_token(
            lifetime_seconds=SHORT_LIVED_TOKEN_LIFESPAN_SECONDS,
        )
