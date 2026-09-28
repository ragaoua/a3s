import httpx
from pydantic import JsonValue

from src.utils import FetchJson


def route_fetch_json(
    routes: dict[str, dict[str, JsonValue] | Exception],
    *,
    captured_urls: list[str] | None = None,
) -> FetchJson:
    """Build a FetchJson stub that routes each call by URL.

    Each route value is either a JSON payload to return or an Exception to raise.
    httpx.Request inputs (used for introspection) are matched on their URL.
    Unmatched URLs raise AssertionError to surface unexpected calls.
    """

    async def _fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        url_str = str(url.url) if isinstance(url, httpx.Request) else url
        if captured_urls is not None:
            captured_urls.append(url_str)
        if url_str not in routes:
            raise AssertionError(f"Unexpected fetch_json call for url: {url_str}")
        result = routes[url_str]
        if isinstance(result, Exception):
            raise result
        return result

    return _fetch_json
