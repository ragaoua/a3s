import json
from typing import Any

import httpx


async def fetch_json(
    url: str | httpx.Request,
    *,
    error_cls: type[Exception] = ValueError,
    error_message: str | None = None,
) -> dict[str, Any]:
    request = url if isinstance(url, httpx.Request) else httpx.Request("GET", url)

    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.send(request)
            response.raise_for_status()

        return json.loads(response.content)
    except (httpx.HTTPError, TimeoutError, json.JSONDecodeError) as err:
        if error_message is None:
            error_message = f"Failed to fetch JSON from '{request.url}'"
        raise error_cls(error_message) from err
