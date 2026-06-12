import os
from collections.abc import Iterator

import httpx
import pytest
from canaille.oidc.basemodels import Client  # pyright: ignore[reportMissingTypeStubs]
from pytest_iam import Server  # pyright: ignore[reportMissingTypeStubs]
from starlette.types import ASGIApp, Receive, Scope, Send

from tests.component.common.iam import IamFixture

_CONFIDENTIAL_CLIENT_ID = "a3s-test-client"
_CONFIDENTIAL_CLIENT_SECRET = "a3s-test-secret"


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
            client_id=_CONFIDENTIAL_CLIENT_ID,
            client_secret=_CONFIDENTIAL_CLIENT_SECRET,
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
        confidential_client_id=_CONFIDENTIAL_CLIENT_ID,
        confidential_client_secret=_CONFIDENTIAL_CLIENT_SECRET,
        _server=iam_server,
        _client=client,
        _user=user,
        _jwk=jwk,  # pyright: ignore[reportUnknownArgumentType]
    )


def build_iam_introspection_guard_app(
    inner: ASGIApp,
    *,
    iam: IamFixture,
) -> ASGIApp:
    """Wrap an ASGI app so it only forwards requests with an iam-valid bearer.

    The guard talks to iam's introspection endpoint directly so the test
    verification stays independent of the project's own OAuth2 middleware.
    """
    introspection_url = f"{iam.base_url}/oauth/introspect"
    client_id = iam.confidential_client_id
    client_secret = iam.confidential_client_secret

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await inner(scope, receive, send)
            return

        auth_header: str | None = None
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                auth_header = value.decode("ascii")
                break

        scheme, _, token = (auth_header or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            await send_unauthorized(send)
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                introspection_url,
                data={"token": token},
                auth=(client_id, client_secret),
            )

        if response.status_code != 200 or response.json().get("active") is not True:
            await send_unauthorized(send)
            return

        await inner(scope, receive, send)

    return app


async def send_unauthorized(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail":"Unauthorized"}',
        }
    )
