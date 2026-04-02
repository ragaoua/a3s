import json
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


def fetch_json(
    url: str | Request,
    *,
    error_cls: type[Exception] = ValueError,
    error_message: str | None = None,
) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=5) as response:
            return json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as err:
        if error_message is None:
            request_url = url.full_url if isinstance(url, Request) else url
            error_message = f"Failed to fetch JSON from '{request_url}'"
        raise error_cls(error_message) from err
