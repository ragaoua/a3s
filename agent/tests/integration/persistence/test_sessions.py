"""Session tests, parametrized over the database backends, plus the default
in-memory session service.

The database-backed tests verify the (app_name, user_id, context_id) mapping
by inspecting the sessions table. The in-memory service has no table to query,
so it is exercised behaviorally: conversation continuity proves the key maps
back to the same session, and subject scoping proves `user_id` is part of it.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic_core import Url
from src.config.types import (
    OAuthConfig,
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
    PersistenceConfig,
)
from tests.common.keycloak import KeycloakFixture
from tests.common.llm import LlmFixture
from tests.integration.common.agent import start_agent_server
from tests.integration.common.persistence import fetch_rows, send_message


def _oauth_config(keycloak: KeycloakFixture) -> OAuthConfig:
    """Inbound oauth2+jwt auth validating tokens minted by the keycloak fixture."""
    return OAuthConfig(
        mode="oauth2",
        issuer_url=Url(keycloak.internal_issuer_url),
        policies=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(keycloak.external_jwks_url)),
            ),
        ),
    )


async def _assert_sessions_scoped_by_subject(
    mock_llm: LlmFixture,
    keycloak: KeycloakFixture,
    persistence_config: PersistenceConfig | None,
) -> str:
    """Create two conversations/sessions that use the same context id but with
    two different token subjects, and assert both sessions are isolated.

    Shared by the in-memory and database-backed scoping tests: the isolation
    guarantee is identical for every backend and verified here behaviorally.
    Returns the context id so a persistent backend can additionally inspect
    how its sessions table recorded the keying.
    """
    context_id = uuid4().hex

    with start_agent_server(
        mock_llm=mock_llm,
        persistence_config=persistence_config,
        auth_config=_oauth_config(keycloak),
    ) as agent_server:
        mock_llm.stub_response("Nice to meet you, Ada!")
        _ = await send_message(
            agent_server.base_url,
            text="My name is Ada.",
            context_id=context_id,
            headers={
                "Authorization": f"Bearer {keycloak.mint_user_access_token('alice')}"
            },
        )

        mock_llm.stub_response("I don't know your name.")
        _ = await send_message(
            agent_server.base_url,
            text="What is my name?",
            context_id=context_id,
            headers={
                "Authorization": f"Bearer {keycloak.mint_user_access_token('bob')}"
            },
        )

    # Bob's LLM call must not have been prompted with any of Alice's
    # conversation, even though he presented the same context id as her.
    messages: list[dict[str, str]] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, bob_message = messages  # pyright: ignore[reportUnusedVariable]

    assert bob_message == {"role": "user", "content": "What is my name?"}

    return context_id


@pytest.mark.asyncio
async def test_conversation_is_stored_in_database(
    mock_llm: LlmFixture,
    persistence_db_connect_string: str,
) -> None:
    persistence_config = PersistenceConfig.model_validate(
        {"connect_string": persistence_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Hello from the mock LLM!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        _ = await send_message(agent_server.base_url, text="hi", context_id=context_id)

    session_rows = await fetch_rows(
        persistence_config.connect_string.get_secret_value(),
        f"SELECT app_name, user_id FROM sessions WHERE id = '{context_id}'",
    )
    event_count_rows = await fetch_rows(
        persistence_config.connect_string.get_secret_value(),
        f"SELECT count(*) AS event_count FROM events WHERE session_id = '{context_id}'",
    )

    assert len(session_rows) == 1
    assert session_rows[0]["app_name"] == "Cody"
    # One event for the user message, one for the agent reply
    assert event_count_rows[0]["event_count"] >= 2


@pytest.mark.asyncio
async def test_session_db_backed_conversation_survives_server_restart(
    mock_llm: LlmFixture,
    persistence_db_connect_string: str,
) -> None:
    persistence_config = PersistenceConfig.model_validate(
        {"connect_string": persistence_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Nice to meet you, Ada!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        _ = await send_message(
            agent_server.base_url, text="My name is Ada.", context_id=context_id
        )

    mock_llm.stub_response("Your name is Ada.")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        task = await send_message(
            agent_server.base_url, text="What is my name?", context_id=context_id
        )

    assert task.artifacts is not None
    assert task.artifacts[0].parts[0].root.kind == "text"
    assert task.artifacts[0].parts[0].root.text == "Your name is Ada."

    # The second LLM call, served by a fresh server process state, must have
    # been prompted with the conversation history loaded from the database.
    messages: dict[str, str] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, first_message, first_response, second_message = messages  # pyright: ignore[reportUnusedVariable]

    assert first_message == {"role": "user", "content": "My name is Ada."}
    assert first_response == {"role": "assistant", "content": "Nice to meet you, Ada!"}
    assert second_message == {"role": "user", "content": "What is my name?"}


@pytest.mark.asyncio
async def test_db_backed_sessions_are_scoped_by_token_subject(
    mock_llm: LlmFixture,
    persistence_db_connect_string: str,
    keycloak: KeycloakFixture,
) -> None:
    """With oauth2+jwt inbound auth, a persistent backend partitions sessions by
    the token's `sub`: a caller reusing another user's context id gets their own
    fresh session instead of resuming the other user's conversation. The keying
    is additionally visible in the sessions table, one row per subject."""
    persistence_config = PersistenceConfig.model_validate(
        {"connect_string": persistence_db_connect_string}
    )

    context_id = await _assert_sessions_scoped_by_subject(
        mock_llm, keycloak, persistence_config
    )

    # The sessions table is keyed by (app_name, user_id, id): the same
    # context id yields one session per authenticated subject.
    rows = await fetch_rows(
        persistence_config.connect_string.get_secret_value(),
        f"SELECT user_id FROM sessions WHERE id = '{context_id}'",
    )

    assert sorted(row["user_id"] for row in rows) == ["alice", "bob"]


@pytest.mark.asyncio
async def test_in_memory_conversation_is_remembered_within_server_lifetime(
    mock_llm: LlmFixture,
) -> None:
    """The default (no `persistence_config`) in-memory service maps (app_name,
    user_id, context_id) to a session in process memory: a follow-up message
    on the same context id is served the earlier exchange as history, with no
    database involved. There is no restart counterpart — surviving a restart
    is exactly what the in-memory service does not do."""
    context_id = uuid4().hex

    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=None,
    ) as agent_server:
        mock_llm.stub_response("Nice to meet you, Ada!")
        _ = await send_message(
            agent_server.base_url, text="My name is Ada.", context_id=context_id
        )

        mock_llm.stub_response("Your name is Ada.")
        task = await send_message(
            agent_server.base_url, text="What is my name?", context_id=context_id
        )

    assert task.artifacts is not None
    assert task.artifacts[0].parts[0].root.kind == "text"
    assert task.artifacts[0].parts[0].root.text == "Your name is Ada."

    # The second call, sharing the context id with the first, must have been
    # prompted with the conversation history held in the in-memory session.
    messages: list[dict[str, str]] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, first_message, first_response, second_message = messages  # pyright: ignore[reportUnusedVariable]

    assert first_message == {"role": "user", "content": "My name is Ada."}
    assert first_response == {"role": "assistant", "content": "Nice to meet you, Ada!"}
    assert second_message == {"role": "user", "content": "What is my name?"}


@pytest.mark.asyncio
async def test_in_memory_sessions_are_scoped_by_token_subject(
    mock_llm: LlmFixture,
    keycloak: KeycloakFixture,
) -> None:
    """The default in-memory service applies the same subject scoping, verified
    purely behaviorally since there is no sessions table to inspect."""
    _ = await _assert_sessions_scoped_by_subject(
        mock_llm, keycloak, persistence_config=None
    )
