import logging

from a2a.server.agent_execution import RequestContext
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
from google.adk.a2a.converters.request_converter import (
    AgentRunRequest,
    convert_a2a_request_to_agent_run_request,
)
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import StreamingMode
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from starlette.applications import Starlette

from src.auth.inbound import (
    ApiKeyAuthMiddleware,
    OAuth2BearerAuthMiddleware,
)
from src.config.types import (
    ApiKeyAuthConfig,
    AuthConfig,
    OAuthConfig,
    ServerConfig,
    SessionsConfig,
)
from src.observability.logging import get_logger

logger = get_logger(__name__)


def _sqlalchemy_db_url(sessions_config: SessionsConfig) -> str:
    """The connect string normalized to its async SQLAlchemy driver."""
    scheme, _, rest = str(sessions_config.connect_string.get_secret_value()).partition(
        "://"
    )
    driver = "sqlite+aiosqlite" if scheme == "sqlite" else "postgresql+asyncpg"
    return f"{driver}://{rest}"


def build_agent_a2a_app(
    *,
    agent: LlmAgent,
    server_config: ServerConfig,
    auth_config: AuthConfig,
    sessions_config: SessionsConfig | None = None,
) -> Starlette:
    adk_logger = logging.getLogger("google_adk")
    adk_logger.setLevel(logging.INFO)

    session_service = (
        DatabaseSessionService(db_url=_sqlalchemy_db_url(sessions_config))
        if sessions_config is not None
        else InMemorySessionService()
    )

    async def create_runner() -> Runner:
        return Runner(
            app_name=agent.name,
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=session_service,
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    agent_executor = A2aAgentExecutor(
        runner=create_runner,
        config=A2aAgentExecutorConfig(request_converter=_request_converter),
        use_legacy=False,
        force_new_version=True,
    )
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
            realm=agent.name,
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
        name=agent.name,
        description=agent.description,
        url=rpc_url,
        version="0.0.1",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id=agent.name,
                name="model",
                description=agent.description,
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


def _request_converter(
    request: RequestContext,
    part_converter,
) -> AgentRunRequest:
    run_request = convert_a2a_request_to_agent_run_request(request, part_converter)
    run_request.run_config.streaming_mode = StreamingMode.SSE
    return run_request
