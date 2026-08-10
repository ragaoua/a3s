import logging
from contextlib import asynccontextmanager

from a2a.server.agent_execution import RequestContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import (
    DatabaseTaskStore,
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    APIKeySecurityScheme,
    AuthorizationCodeOAuthFlow,
    OAuth2SecurityScheme,
    OAuthFlows,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from a2a.utils.constants import (
    DEFAULT_RPC_URL,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
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
    PersistenceConfig,
    ServerConfig,
)
from src.observability.logging import get_logger

logger = get_logger(__name__)


def _sqlalchemy_db_url(persistence_config: PersistenceConfig) -> str:
    """The connect string normalized to its async SQLAlchemy driver."""
    scheme, _, rest = str(
        persistence_config.connect_string.get_secret_value()
    ).partition("://")
    driver = "sqlite+aiosqlite" if scheme == "sqlite" else "postgresql+asyncpg"
    return f"{driver}://{rest}"


def build_agent_a2a_app(
    *,
    agent: LlmAgent,
    server_config: ServerConfig,
    auth_config: AuthConfig,
    persistence_config: PersistenceConfig | None = None,
) -> Starlette:
    adk_logger = logging.getLogger("google_adk")
    adk_logger.setLevel(logging.INFO)

    if persistence_config is not None:
        db_url = _sqlalchemy_db_url(persistence_config)
        session_service = DatabaseSessionService(db_url=db_url)
        task_store = DatabaseTaskStore(engine=session_service.db_engine)
    else:
        session_service = InMemorySessionService()
        task_store = InMemoryTaskStore()

    async def create_runner() -> Runner:
        return Runner(
            app_name=agent.name,
            agent=agent,
            session_service=session_service,
            memory_service=InMemoryMemoryService(),
        )

    agent_executor = A2aAgentExecutor(
        runner=create_runner,
        config=A2aAgentExecutorConfig(request_converter=_request_converter),
        use_legacy=False,
        force_new_version=True,
    )
    rpc_url = f"http://{server_config.listen_address}:{server_config.listen_port}"

    if isinstance(auth_config, ApiKeyAuthConfig):
        security_schemes = {
            "APIKeySecurityScheme": SecurityScheme(
                api_key_security_scheme=APIKeySecurityScheme(
                    location="header",
                    name=auth_config.header_name,
                )
            ),
        }
        security_requirements = [
            SecurityRequirement(
                schemes={"APIKeySecurityScheme": StringList()},
            )
        ]
    elif isinstance(auth_config, OAuthConfig):
        security_schemes = {
            "OAuth2SecurityScheme": SecurityScheme(
                oauth2_security_scheme=OAuth2SecurityScheme(
                    flows=OAuthFlows(
                        authorization_code=AuthorizationCodeOAuthFlow(
                            # TODO(#47): Populate a usable flow from provider metadata.
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
        security_requirements = [
            SecurityRequirement(
                schemes={"OAuth2SecurityScheme": StringList()},
            )
        ]
    else:
        security_schemes = None
        security_requirements = []

    agent_card = AgentCard(
        name=agent.name,
        description=agent.description,
        # A2A 1.0 replaced the card's single `url` with a list of transport
        # bindings. We speak JSON-RPC only, on the RPC route mounted below.
        supported_interfaces=[
            AgentInterface(
                url=rpc_url,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        version="0.0.1",
        capabilities=AgentCapabilities(
            streaming=True,
            # TODO: maybe this is interesting.
            # We would provide an extended agent card to authorized users
            # to, for instance, be able to see what MCP tools the agent has
            # access to
            extended_agent_card=False,
        ),
        skills=[
            AgentSkill(
                id=agent.name,
                name="model",
                description=agent.description,
                tags=["llm"],
            )
        ],
        security_schemes=security_schemes,
        security_requirements=security_requirements,
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    @asynccontextmanager
    async def lifespan(_: Starlette):
        try:
            yield
        finally:
            try:
                await request_handler.aclose()
            finally:
                if isinstance(session_service, DatabaseSessionService):
                    await session_service.close()

    app = Starlette(lifespan=lifespan)
    if isinstance(auth_config, ApiKeyAuthConfig):
        app.add_middleware(
            ApiKeyAuthMiddleware,
            api_key=auth_config.api_key,
            header_name=auth_config.header_name,
        )
    elif isinstance(auth_config, OAuthConfig):
        app.add_middleware(
            OAuth2BearerAuthMiddleware,
            issuer_url=str(auth_config.issuer_url),
            realm=agent.name,
            config=auth_config.policies,
        )

    app.routes.extend(
        [
            *create_agent_card_routes(agent_card),
            *create_jsonrpc_routes(request_handler, DEFAULT_RPC_URL),
        ]
    )
    return app


def _request_converter(
    request: RequestContext,
    part_converter,
) -> AgentRunRequest:
    run_request = convert_a2a_request_to_agent_run_request(request, part_converter)
    run_request.run_config.streaming_mode = StreamingMode.SSE
    return run_request
