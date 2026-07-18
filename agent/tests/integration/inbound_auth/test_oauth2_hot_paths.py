from uuid import uuid4

import httpx
import pytest
from a2a.client import A2AClient, A2AClientHTTPError
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)

from tests.common.a2a import (
    A2aServerFixture,
    create_send_message_payload,
    wait_for_agent_card,
)
from tests.common.keycloak import KeycloakFixture


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_with_valid_jwt_bearer(
    agent_with_jwt_inbound_auth: A2aServerFixture,
    keycloak: KeycloakFixture,
) -> None:
    """Happy path: a valid bearer JWT minted by Keycloak passes the agent's
    OAuth2 middleware (signature verified against Keycloak's JWKS, iss matches
    the configured issuer), and the a2a request flows through to the stubbed
    LLM."""
    token = keycloak.mint_user_access_token()
    agent_with_jwt_inbound_auth.mock_llm.stub_response("Authorized response.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_jwt_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    task = response.root.result
    assert task.artifacts is not None

    text_parts = [
        part.root.text
        for artifact in task.artifacts
        for part in artifact.parts
        if part.root.kind == "text"
    ]
    assert "Authorized response." in text_parts


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_with_valid_bearer_via_introspection(
    agent_with_introspection_inbound_auth: A2aServerFixture,
    keycloak: KeycloakFixture,
) -> None:
    """Happy path: the middleware POSTs the bearer to Keycloak's introspection
    endpoint, Keycloak responds active=true, and the a2a request proceeds."""
    token = keycloak.mint_user_access_token()
    agent_with_introspection_inbound_auth.mock_llm.stub_response("Authorized response.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_introspection_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    task = response.root.result
    assert task.artifacts is not None

    text_parts = [
        part.root.text
        for artifact in task.artifacts
        for part in artifact.parts
        if part.root.kind == "text"
    ]
    assert "Authorized response." in text_parts


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_invalid_bearer_token(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_jwt_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={"Authorization": "Bearer not-a-real-token"},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        with pytest.raises(A2AClientHTTPError) as exc:
            _ = await client.send_message(request)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_without_authorization_header(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_jwt_inbound_auth.base_url, httpx_client
        )
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        with pytest.raises(A2AClientHTTPError) as exc:
            _ = await client.send_message(request)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_non_bearer_authorization_scheme(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_jwt_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        with pytest.raises(A2AClientHTTPError) as exc:
            _ = await client.send_message(request)

    assert exc.value.status_code == 401
