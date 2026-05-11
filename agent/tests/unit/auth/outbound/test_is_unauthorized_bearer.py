import httpx

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth


def test_is_unauthorized_bearer_requires_401_and_bearer_header() -> None:
    assert OAuthClientCredentialsAuth._is_unauthorized_bearer(  # pyright: ignore[reportPrivateUsage]
        httpx.Response(
            401,
            headers=[
                ("WWW-Authenticate", "Digest realm=test"),
                ("WWW-Authenticate", "Bearer realm=test"),
            ],
        )
    )
    assert not OAuthClientCredentialsAuth._is_unauthorized_bearer(  # pyright: ignore[reportPrivateUsage]
        httpx.Response(401, headers={"WWW-Authenticate": "Digest realm=test"})
    )
    assert not OAuthClientCredentialsAuth._is_unauthorized_bearer(  # pyright: ignore[reportPrivateUsage]
        httpx.Response(403, headers={"WWW-Authenticate": "Bearer realm=test"})
    )
