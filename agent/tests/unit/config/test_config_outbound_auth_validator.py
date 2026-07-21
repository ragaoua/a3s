from typing import Literal
import pytest
from pydantic import SecretStr, ValidationError
from pydantic_core import Url

from src.config import Config
from src.config.types import (
    AgentConfig,
    ApiKeyAuthConfig,
    LlmConfig,
    McpServerConfig,
    OAuthClientCredentialsAuthConfig,
    OAuthConfig,
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthTokenForwardAuthConfig,
    OutboundApiKeyAuthConfig,
    SubagentConfig,
)
from src.config.types.auth import OAuthDiscoveredJwksPolicyConfig
from src.config.types.outbound_auth import OAuthStaticTokenExchangeAuthConfig


VALID_LLM = LlmConfig(
    api_url=Url("http://example.com"),
    api_key=SecretStr("k"),
    model="m",
)
AGENT_NO_SUBAGENTS = AgentConfig(
    name="a",
    description="d",
    instructions="i",
)
ROOT_OAUTH = OAuthConfig(
    mode="oauth2",
    issuer_url=Url("http://issuer.example.com"),
    policies=OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=OAuthDiscoveredJwksPolicyConfig()),
    ),
)
ROOT_API_KEY = ApiKeyAuthConfig(mode="api_key", api_key=SecretStr("k"))

TOKEN_FORWARD = OAuthTokenForwardAuthConfig(mode="oauth_token_forward")
TOKEN_EXCHANGE_DISCOVERED = OAuthDiscoveredTokenExchangeAuthConfig(
    mode="oauth_token_exchange",
    client_id="c",
    client_secret=SecretStr("s"),
    issuer_url=Url("http://example.com"),
)
TOKEN_EXCHANGE_STATIC = OAuthStaticTokenExchangeAuthConfig(
    mode="oauth_token_exchange",
    client_id="c",
    client_secret=SecretStr("s"),
    token_endpoint=Url("http://idp.example.com/token"),
)
CLIENT_CREDENTIALS = OAuthClientCredentialsAuthConfig(
    mode="oauth_client_credentials",
    client_id="c",
    client_secret=SecretStr("s"),
    token_endpoint=Url("http://idp.example.com/token"),
)


def _mcp_server(
    auth: OAuthTokenForwardAuthConfig
    | OAuthClientCredentialsAuthConfig
    | OAuthDiscoveredTokenExchangeAuthConfig
    | OAuthStaticTokenExchangeAuthConfig
    | Literal["none"],
) -> McpServerConfig:
    return McpServerConfig(url=Url("http://mcp.example.com"), auth=auth)


def _subagent(
    auth: OAuthTokenForwardAuthConfig
    | OAuthClientCredentialsAuthConfig
    | OAuthDiscoveredTokenExchangeAuthConfig
    | OAuthStaticTokenExchangeAuthConfig
    | OutboundApiKeyAuthConfig
    | Literal["none"],
) -> SubagentConfig:
    return SubagentConfig(url=Url("http://sub.example.com"), type="peer", auth=auth)


def _error_msgs(exc: ValidationError) -> list[str]:
    return [error["msg"] for error in exc.errors(include_url=False)]


@pytest.mark.parametrize(
    ("server_auth", "expected_mode"),
    [
        (TOKEN_FORWARD, "oauth_token_forward"),
        (TOKEN_EXCHANGE_DISCOVERED, "oauth_token_exchange"),
        (TOKEN_EXCHANGE_STATIC, "oauth_token_exchange"),
    ],
)
@pytest.mark.parametrize("auth_config", ["none", ROOT_API_KEY])
def test_mcp_server_token_modes_require_root_oauth2(
    server_auth: OAuthTokenForwardAuthConfig
    | OAuthDiscoveredTokenExchangeAuthConfig
    | OAuthStaticTokenExchangeAuthConfig,
    expected_mode: str,
    auth_config: Literal["none"] | ApiKeyAuthConfig,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Config(  # pyright: ignore[reportUnusedCallResult]
            llm=VALID_LLM,
            agent=AGENT_NO_SUBAGENTS,
            auth=auth_config,
            mcp_servers=[_mcp_server(server_auth)],
        )

    assert any(
        f"`mcp_servers[0].auth.mode` '{expected_mode}' requires root-level `auth.mode: 'oauth2'`"
        in msg
        for msg in _error_msgs(exc_info.value)
    )


@pytest.mark.parametrize(
    ("subagent_auth", "expected_mode"),
    [
        (TOKEN_FORWARD, "oauth_token_forward"),
        (TOKEN_EXCHANGE_DISCOVERED, "oauth_token_exchange"),
        (TOKEN_EXCHANGE_STATIC, "oauth_token_exchange"),
    ],
)
@pytest.mark.parametrize("auth_config", ["none", ROOT_API_KEY])
def test_subagent_token_modes_require_root_oauth2(
    subagent_auth: OAuthTokenForwardAuthConfig
    | OAuthDiscoveredTokenExchangeAuthConfig
    | OAuthStaticTokenExchangeAuthConfig,
    expected_mode: str,
    auth_config: Literal["none"] | ApiKeyAuthConfig,
) -> None:
    agent = AGENT_NO_SUBAGENTS.model_copy()
    agent.subagents = {"helper": _subagent(subagent_auth)}

    with pytest.raises(ValidationError) as exc_info:
        Config(  # pyright: ignore[reportUnusedCallResult]
            llm=VALID_LLM,
            agent=agent,
            auth=auth_config,
        )

    assert any(
        f"`agent.subagents['helper'].auth.mode` '{expected_mode}' requires root-level `auth.mode: 'oauth2'`"
        in msg
        for msg in _error_msgs(exc_info.value)
    )


@pytest.mark.parametrize(
    "auth",
    [
        TOKEN_FORWARD,
        TOKEN_EXCHANGE_DISCOVERED,
        TOKEN_EXCHANGE_STATIC,
    ],
)
def test_token_modes_pass_when_root_auth_is_oauth2(
    auth: OAuthTokenForwardAuthConfig
    | OAuthDiscoveredTokenExchangeAuthConfig
    | OAuthStaticTokenExchangeAuthConfig,
) -> None:
    agent = AGENT_NO_SUBAGENTS.model_copy()
    agent.subagents = {"helper": _subagent(TOKEN_EXCHANGE_DISCOVERED)}

    config = Config(
        llm=VALID_LLM,
        agent=agent,
        auth=ROOT_OAUTH,
        mcp_servers=[_mcp_server(auth)],
    )

    assert isinstance(config.auth, OAuthConfig)


def test_discovered_token_exchange_gets_issuer_url_resolved_from_root_oauth2() -> None:
    agent = AGENT_NO_SUBAGENTS.model_copy()
    agent.subagents = {"helper": _subagent(TOKEN_EXCHANGE_DISCOVERED)}

    config = Config(
        llm=VALID_LLM,
        agent=agent,
        auth=ROOT_OAUTH,
        mcp_servers=[_mcp_server(TOKEN_EXCHANGE_DISCOVERED)],
    )

    mcp_auth = config.mcp_servers[0].auth
    assert isinstance(mcp_auth, OAuthDiscoveredTokenExchangeAuthConfig)
    assert mcp_auth.issuer_url == ROOT_OAUTH.issuer_url

    subagent_auth = config.agent.subagents["helper"].auth
    assert isinstance(subagent_auth, OAuthDiscoveredTokenExchangeAuthConfig)
    assert subagent_auth.issuer_url == ROOT_OAUTH.issuer_url


def test_oauth_client_credentials_does_not_require_root_oauth2() -> None:
    agent = AGENT_NO_SUBAGENTS.model_copy()
    agent.subagents = {"helper": _subagent(CLIENT_CREDENTIALS)}

    config = Config(
        llm=VALID_LLM,
        agent=agent,
        auth="none",
        mcp_servers=[_mcp_server(CLIENT_CREDENTIALS)],
    )

    assert config.auth == "none"
