import json

import httpx
import pytest

from src.utils import fetch_json


@pytest.mark.asyncio
async def test_fetch_json_returns_parsed_body_for_url_string() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://api.example/data"
        return httpx.Response(200, json={"foo": "bar"})

    result = await fetch_json(
        "https://api.example/data",
        transport=httpx.MockTransport(handler),
    )

    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_fetch_json_returns_parsed_body_for_request_input() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    custom_request = httpx.Request(
        "POST",
        "https://api.example/data",
        content=b"payload",
    )
    result = await fetch_json(
        custom_request,
        transport=httpx.MockTransport(handler),
    )

    assert result == {"ok": True}
    assert captured[0].method == "POST"
    assert captured[0].content == b"payload"


@pytest.mark.asyncio
async def test_fetch_json_wraps_http_status_error_in_default_error_cls() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        return httpx.Response(500)

    with pytest.raises(ValueError) as exc_info:
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.asyncio
async def test_fetch_json_wraps_network_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        raise httpx.ConnectError("connection refused")

    with pytest.raises(ValueError) as exc_info:
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)


@pytest.mark.asyncio
async def test_fetch_json_wraps_httpx_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        raise httpx.TimeoutException("too slow")

    with pytest.raises(ValueError) as exc_info:
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, httpx.TimeoutException)


@pytest.mark.asyncio
async def test_fetch_json_wraps_builtin_timeout_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        raise TimeoutError("asyncio timed out")

    with pytest.raises(ValueError) as exc_info:
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, TimeoutError)


@pytest.mark.asyncio
async def test_fetch_json_wraps_invalid_json_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        return httpx.Response(200, content=b"not json")

    with pytest.raises(ValueError) as exc_info:
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


@pytest.mark.asyncio
async def test_fetch_json_uses_custom_error_cls() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        return httpx.Response(500)

    with pytest.raises(RuntimeError):
        _ = await fetch_json(
            "https://api.example/data",
            error_cls=RuntimeError,
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_fetch_json_uses_custom_error_message() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        return httpx.Response(500)

    with pytest.raises(ValueError, match="^custom message$"):
        _ = await fetch_json(
            "https://api.example/data",
            error_message="custom message",
            transport=httpx.MockTransport(handler),
        )


@pytest.mark.asyncio
async def test_fetch_json_default_error_message_includes_request_url() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pyright: ignore[reportUnusedParameter]
        raise httpx.ConnectError("oops")

    with pytest.raises(ValueError, match="https://api.example/data"):
        _ = await fetch_json(
            "https://api.example/data",
            transport=httpx.MockTransport(handler),
        )
