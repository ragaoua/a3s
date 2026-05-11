import base64

from pydantic import SecretStr

from src.auth.oauth_client_auth import build_client_authenticated_request


def test_basic_auth_percent_encodes_credentials_before_base64():
    # RFC 6749 §2.3.1 / Appendix B: client_id and client_secret MUST be
    # application/x-www-form-urlencoded before being joined with ":" and
    # base64-encoded into the Basic header. Otherwise meta-characters like
    # "+" and "&" round-trip to the wrong value at the authorization server.
    request = build_client_authenticated_request(
        url="https://issuer.example/oauth/token",
        body={"grant_type": "client_credentials"},
        auth_method="client_secret_basic",
        client_id="client+id",
        client_secret=SecretStr("secret&value"),
    )

    assert request.headers["Authorization"] == "Basic " + base64.b64encode(
        b"client%2Bid:secret%26value"
    ).decode("ascii")
