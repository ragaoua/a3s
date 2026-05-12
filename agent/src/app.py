from starlette.applications import Starlette

from src.a2a import create_a2a_app
from src.agent import build_agent
from src.auth.inbound import (
    ApiKeyAuthMiddleware,
    OAuth2BearerAuthMiddleware,
)
from src.config import Config
from src.config.types import (
    ApiKeyAuthConfig,
    OAuthConfig,
)
from src.logging import get_logger
from src.telemetry import TracingMiddleware

logger = get_logger(__name__)


def build_app(config: Config) -> Starlette:
    agent = build_agent(
        llm_config=config.llm,
        agent_config=config.agent,
        mcp_servers_config=config.mcp_servers,
    )
    app = create_a2a_app(
        agent=agent,
        server_config=config.server,
        auth_config=config.auth,
    )
    auth_mode = "none"

    if isinstance(config.auth, ApiKeyAuthConfig):
        logger.info("Auth mode: API Key")
        auth_mode = "api_key"
        app.add_middleware(
            ApiKeyAuthMiddleware,
            api_key=config.auth.api_key.get_secret_value(),
        )
    elif isinstance(config.auth, OAuthConfig):
        logger.info("Auth mode: OAuth2")
        auth_mode = "oauth2"

        app.add_middleware(
            OAuth2BearerAuthMiddleware,
            issuer_url=str(config.auth.issuer_url),
            realm=agent.name,
            config=config.auth.policies,
        )
    else:
        logger.info("Auth disabled.")

    app.add_middleware(
        TracingMiddleware,
        agent_name=config.agent.name,
        auth_mode=auth_mode,
    )

    return app
