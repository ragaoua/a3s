import pytest

from tests.common.a2a import (
    A2aServerFixture,
    get_artifact_text_parts,
    post_rpc,
    send_message,
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

    task = await send_message(
        agent_with_jwt_inbound_auth.base_url,
        text="ping",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert "Authorized response." in get_artifact_text_parts(task)


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_with_valid_bearer_via_introspection(
    agent_with_introspection_inbound_auth: A2aServerFixture,
    keycloak: KeycloakFixture,
) -> None:
    """Happy path: the middleware POSTs the bearer to Keycloak's introspection
    endpoint, Keycloak responds active=true, and the a2a request proceeds."""
    token = keycloak.mint_user_access_token()
    agent_with_introspection_inbound_auth.mock_llm.stub_response("Authorized response.")

    task = await send_message(
        agent_with_introspection_inbound_auth.base_url,
        text="ping",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert "Authorized response." in get_artifact_text_parts(task)


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_invalid_bearer_token(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    response = await post_rpc(
        agent_with_jwt_inbound_auth.base_url,
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_without_authorization_header(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    response = await post_rpc(agent_with_jwt_inbound_auth.base_url)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_non_bearer_authorization_scheme(
    agent_with_jwt_inbound_auth: A2aServerFixture,
) -> None:
    response = await post_rpc(
        agent_with_jwt_inbound_auth.base_url,
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )

    assert response.status_code == 401
