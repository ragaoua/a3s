import pytest
from a2a.client.middleware import ClientCallContext
from a2a.types import Message, Part, Role, TextPart
from google.adk.a2a.agent.config import ParametersConfig

from src.auth.context import bind_current_authorization_header
from src.agent.subagents import _token_forward_before_request  # pyright: ignore[reportPrivateUsage]


def _message() -> Message:
    return Message(
        message_id="m-1",
        role=Role.user,
        parts=[Part(root=TextPart(text="hi"))],
    )


@pytest.mark.asyncio
async def test_token_forward_no_op_when_no_inbound_authorization_header() -> None:
    request = _message()
    params = ParametersConfig()

    returned_request, returned_params = await _token_forward_before_request(
        _=None,  # pyright: ignore[reportArgumentType]
        a2a_request=request,
        params=params,
    )

    assert returned_request is request
    assert returned_params is params
    assert returned_params.client_call_context is None


@pytest.mark.asyncio
async def test_token_forward_initializes_client_call_context_when_missing() -> None:
    params = ParametersConfig()

    with bind_current_authorization_header("Bearer abc"):
        _, returned_params = await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=_message(),
            params=params,
        )

    assert isinstance(returned_params.client_call_context, ClientCallContext)
    assert returned_params.client_call_context.state["http_kwargs"]["headers"] == {
        "Authorization": "Bearer abc"
    }


@pytest.mark.asyncio
async def test_token_forward_injects_header_into_existing_context() -> None:
    existing_context = ClientCallContext()
    params = ParametersConfig(client_call_context=existing_context)

    with bind_current_authorization_header("Bearer xyz"):
        _, returned_params = await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=_message(),
            params=params,
        )

    assert returned_params.client_call_context is existing_context
    assert existing_context.state["http_kwargs"]["headers"] == {
        "Authorization": "Bearer xyz"
    }


@pytest.mark.asyncio
async def test_token_forward_preserves_existing_http_kwargs_and_headers() -> None:
    existing_context = ClientCallContext()
    existing_context.state["http_kwargs"] = {
        "timeout": 30,
        "headers": {"X-Trace-Id": "trace-1"},
    }
    params = ParametersConfig(client_call_context=existing_context)

    with bind_current_authorization_header("Bearer xyz"):
        await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=_message(),
            params=params,
        )

    http_kwargs = existing_context.state["http_kwargs"]
    assert http_kwargs["timeout"] == 30
    assert http_kwargs["headers"] == {
        "X-Trace-Id": "trace-1",
        "Authorization": "Bearer xyz",
    }


@pytest.mark.asyncio
async def test_token_forward_treats_empty_string_header_as_no_op() -> None:
    request = _message()
    params = ParametersConfig()

    with bind_current_authorization_header(""):
        returned_request, returned_params = await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=request,
            params=params,
        )

    assert returned_params.client_call_context is None
    assert returned_request is request
