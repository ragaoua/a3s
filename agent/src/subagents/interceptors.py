from a2a.client.middleware import ClientCallContext
from a2a.types import Message
from google.adk.a2a.agent.config import ParametersConfig
from google.adk.agents import InvocationContext

from src.auth.context import get_current_authorization_header


async def token_forward_before_request(
    _: InvocationContext,
    a2a_request: Message,
    params: ParametersConfig,
) -> tuple[Message, ParametersConfig]:
    """Forward the inbound `Authorization` header onto the outbound A2A request.

    No-op when no inbound header is present. Initializes a `ClientCallContext`
    if the params don't already carry one.
    """
    authorization_header = get_current_authorization_header()
    if not authorization_header:
        return a2a_request, params

    if params.client_call_context is None:
        params.client_call_context = ClientCallContext()

    http_kwargs = params.client_call_context.state.get("http_kwargs", {})
    headers = http_kwargs.get("headers", {})
    headers["Authorization"] = authorization_header
    http_kwargs["headers"] = headers
    params.client_call_context.state["http_kwargs"] = http_kwargs

    return a2a_request, params
