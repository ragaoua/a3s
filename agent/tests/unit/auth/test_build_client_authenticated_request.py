import base64
from urllib.parse import parse_qs

from pydantic import SecretStr

from src.auth.oauth_client_auth import build_client_authenticated_request


def test_returns_post_request_with_form_urlencoded_body() -> None:
    request = build_client_authenticated_request(
        url="https://issuer.example/oauth/token",
        body={"grant_type": "client_credentials"},
        auth_method="client_secret_basic",
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
    )

    assert request.method == "POST"
    assert str(request.url) == "https://issuer.example/oauth/token"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_client_secret_basic_uses_authorization_header() -> None:
    request = build_client_authenticated_request(
        url="https://issuer.example/oauth/token",
        body={"grant_type": "client_credentials"},
        auth_method="client_secret_basic",
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
    )

    assert request.headers["Authorization"] == "Basic " + base64.b64encode(
        b"client-id:client-secret"
    ).decode("ascii")
    assert parse_qs(request.content.decode("utf-8")) == {
        "grant_type": ["client_credentials"]
    }


def test_client_secret_post_appends_credentials_to_body() -> None:
    request = build_client_authenticated_request(
        url="https://issuer.example/oauth/token",
        body={"grant_type": "client_credentials"},
        auth_method="client_secret_post",
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
    )

    assert "Authorization" not in request.headers
    assert parse_qs(request.content.decode("utf-8")) == {
        "grant_type": ["client_credentials"],
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
    }


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
