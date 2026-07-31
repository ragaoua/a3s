import pytest
from a2a.client import ClientCallContext
from a2a.helpers import new_text_message
from a2a.types import Message, Role
from google.adk.a2a.agent.config import ParametersConfig

from src.auth.context import bind_current_authorization_header
from src.agent.subagents import _token_forward_before_request  # pyright: ignore[reportPrivateUsage]


def _message() -> Message:
    return new_text_message("hi", role=Role.ROLE_USER)


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
async def test_token_forward_treats_empty_string_header_as_no_op() -> None:
    request = _message()
    params = ParametersConfig()

    with bind_current_authorization_header(""):
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
    assert returned_params.client_call_context.service_parameters == {
        "Authorization": "Bearer abc"
    }


@pytest.mark.asyncio
async def test_token_forward_injects_header_into_existing_context_preserving_service_parameters() -> (
    None
):
    existing_context = ClientCallContext(
        service_parameters={"X-Trace-Id": "trace-1"},
        timeout=30,
    )
    params = ParametersConfig(client_call_context=existing_context)

    with bind_current_authorization_header("Bearer xyz"):
        _, returned_params = await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=_message(),
            params=params,
        )

    assert returned_params.client_call_context is existing_context
    assert existing_context.timeout == 30
    assert existing_context.service_parameters == {
        "X-Trace-Id": "trace-1",
        "Authorization": "Bearer xyz",
    }


@pytest.mark.asyncio
async def test_token_forward_overwrites_a_stale_authorization_parameter() -> None:
    existing_context = ClientCallContext(
        service_parameters={"Authorization": "Bearer stale"}
    )
    params = ParametersConfig(client_call_context=existing_context)

    with bind_current_authorization_header("Bearer fresh"):
        _, returned_params = await _token_forward_before_request(
            _=None,  # pyright: ignore[reportArgumentType]
            a2a_request=_message(),
            params=params,
        )

    assert returned_params.client_call_context is existing_context
    assert existing_context.service_parameters == {"Authorization": "Bearer fresh"}
