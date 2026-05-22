import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from pydantic import JsonValue
import pytest
from authlib.jose import jwt
from canaille.core.models import User  # pyright: ignore[reportMissingTypeStubs]
from canaille.oidc.basemodels import Client  # pyright: ignore[reportMissingTypeStubs]
from pytest_iam import Server  # pyright: ignore[reportMissingTypeStubs]

CONFIDENTIAL_CLIENT_ID = "a3s-test-client"
CONFIDENTIAL_CLIENT_SECRET = "a3s-test-secret"
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


@pytest.fixture(scope="session")
def iam(iam_server: Server) -> Iterator[IamFixture]:
    # pytest-iam's iam_configuration sets AUTHLIB_INSECURE_TRANSPORT=1 in the
    # process env (pytest_iam/__init__.py:186) and never cleans it up. The flag
    # isn't needed for the default localhost binding (authlib's
    # is_secure_transport already whitelists http://localhost: and
    # http://127.0.0.1:), and leaving it set leaks into unrelated tests that
    # assert on https-only validation. Pop it once so the rest of the session
    # sees a clean env; tests that want the flag can still set it locally
    # (e.g. via monkeypatch.setenv).
    _ = os.environ.pop("AUTHLIB_INSECURE_TRANSPORT", None)
    with iam_server.app.app_context():
        client: Client = iam_server.models.Client(  # pyright: ignore[reportAny]
            client_id=CONFIDENTIAL_CLIENT_ID,
            client_secret=CONFIDENTIAL_CLIENT_SECRET,
            client_name="a3s-test",
            grant_types=["client_credentials"],
            response_types=["token"],
            token_endpoint_auth_method="client_secret_basic",
            scope=["openid"],
        )
        iam_server.backend.save(client)  # pyright: ignore[reportUnknownMemberType]
        client.audience = [client]
        iam_server.backend.save(client)  # pyright: ignore[reportUnknownMemberType]

        user = iam_server.random_user()  # pyright: ignore[reportUnknownMemberType]

    base_url = iam_server.url.rstrip("/")
    jwk = iam_server.app.config["CANAILLE_OIDC"]["ACTIVE_JWKS"][0]  # pyright: ignore[reportUnknownVariableType]

    yield IamFixture(
        base_url=base_url,
        issuer_url=base_url,
        jwks_url=f"{base_url}/oauth/jwks.json",
        confidential_client_id=CONFIDENTIAL_CLIENT_ID,
        confidential_client_secret=CONFIDENTIAL_CLIENT_SECRET,
        _server=iam_server,
        _client=client,
        _user=user,
        _jwk=jwk,  # pyright: ignore[reportUnknownArgumentType]
    )
