from typing import Literal

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    APIKeySecurityScheme,
    AuthorizationCodeOAuthFlow,
    In,
    OAuth2SecurityScheme,
    OAuthFlows,
    SecurityScheme,
)
from authlib.oauth2.rfc8414 import get_well_known_url
from starlette.applications import Starlette

from src.a2a.executor import LangGraphAgentExecutor
from src.agent import LangChainAgent
from src.auth.inbound import (
    ApiKeyAuthMiddleware,
    OAuth2BearerAuthMiddleware,
)
from src.config.types import (
    AgentConfig,
    ApiKeyAuthConfig,
    OAuthConfig,
    ServerConfig,
)


def build_agent_a2a_app(
    *,
    agent: LangChainAgent,
    agent_config: AgentConfig,
    server_config: ServerConfig,
    auth_config: OAuthConfig | ApiKeyAuthConfig | Literal["none"],
) -> Starlette:
    agent_executor = LangGraphAgentExecutor(agent)
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore(),
        push_config_store=InMemoryPushNotificationConfigStore(),
    )

    rpc_url = f"http://{server_config.listen_address}:{server_config.listen_port}"

    app = Starlette()

    if isinstance(auth_config, ApiKeyAuthConfig):
        app.add_middleware(
            ApiKeyAuthMiddleware,
            api_key=auth_config.api_key.get_secret_value(),
        )
        security_schemes = {
            "APIKeySecurityScheme": SecurityScheme(
                APIKeySecurityScheme(
                    in_=In.header,
                    name=ApiKeyAuthMiddleware.HEADER_NAME,
                )
            ),
        }
    elif isinstance(auth_config, OAuthConfig):
        app.add_middleware(
            OAuth2BearerAuthMiddleware,
            issuer_url=str(auth_config.issuer_url),
            realm=agent_config.name,
            config=auth_config.policies,
        )
        security_schemes = {
            "OAuth2SecurityScheme": SecurityScheme(
                OAuth2SecurityScheme(
                    flows=OAuthFlows(
                        authorization_code=AuthorizationCodeOAuthFlow(
                            # TODO
                            authorization_url="",
                            refresh_url="",
                            scopes={},
                            token_url="",
                        )
                    ),
                    oauth2_metadata_url=get_well_known_url(
                        str(auth_config.issuer_url), external=True
                    ),
                )
            ),
        }
    else:
        security_schemes = None

    agent_card = AgentCard(
        name=agent_config.name,
        description=agent_config.description,
        url=rpc_url,
        version="0.0.1",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id=agent_config.name,
                name="model",
                description=agent_config.description,
                tags=["llm"],
            )
        ],
        security_schemes=security_schemes,
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        # TODO: maybe this is interesting.
        # We would provide an extended agent card to authorized users
        # to, for instance, be able to see what MCP tools the agent has
        # access to
        supports_authenticated_extended_card=False,
    )

    a2a_server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    a2a_server.add_routes_to_app(app)
    return app
