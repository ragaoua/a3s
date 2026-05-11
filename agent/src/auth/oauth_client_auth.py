import base64
from typing import Literal
from urllib.parse import quote_plus, urlencode

import httpx
from pydantic import SecretStr


def build_client_authenticated_request(
    *,
    url: str,
    body: dict[str, str],
    auth_method: Literal["client_secret_basic", "client_secret_post"],
    client_id: str,
    client_secret: SecretStr,
) -> httpx.Request:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if auth_method == "client_secret_basic":
        # RFC 6749 §2.3.1 / Appendix B: form-urlencode both values
        # before joining with ":" and base64-encoding.
        encoded_credentials = (
            f"{quote_plus(client_id)}:{quote_plus(client_secret.get_secret_value())}"
        )
        headers["Authorization"] = "Basic " + base64.b64encode(
            encoded_credentials.encode("utf-8")
        ).decode("ascii")
    else:
        body = {
            **body,
            "client_id": client_id,
            "client_secret": client_secret.get_secret_value(),
        }

    return httpx.Request(
        method="POST",
        url=url,
        headers=headers,
        content=urlencode(body).encode("utf-8"),
    )
