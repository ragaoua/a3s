import base64

from pydantic import SecretStr
from pydantic_core import Url

from src.auth.outbound import OAuthClientCredentialsAuth
from src.config.types import OAuthClientCredentialsAuthConfig


def test_fetch_access_token_from_auth_server_basic_auth_percent_encodes_credentials():
    # RFC 6749 §2.3.1 / Appendix B: client_id and client_secret MUST be
    # application/x-www-form-urlencoded before being joined with ":" and
    # base64-encoded into the Basic header. Otherwise meta-characters like
    # "+" and "&" round-trip to the wrong value at the authorization server.
    server_auth_config = OAuthClientCredentialsAuthConfig(
        mode="oauth_client_credentials",
        token_endpoint=Url("https://issuer.example/oauth/token"),
        client_id="client+id",
        client_secret=SecretStr("secret&value"),
        auth_method="client_secret_basic",
    )

    request = OAuthClientCredentialsAuth._build_token_request(server_auth_config)  # pyright: ignore[reportPrivateUsage]

    assert request.headers["Authorization"] == "Basic " + base64.b64encode(
        b"client%2Bid:secret%26value"
    ).decode("ascii")
