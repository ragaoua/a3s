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
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from starlette.applications import Starlette

from src.auth import ApiKeyAuthMiddleware, OAuth2BearerAuthMiddleware
from src.config import Config
from src.config.types import (
    ApiKeyAuthConfig,
    OAuthConfig,
)
from src.logging import get_logger
from src.mcp import get_mcp_tool_set

logger = get_logger(__name__)


def request_converter(
    request: RequestContext,
    part_converter,
) -> AgentRunRequest:
    run_request = convert_a2a_request_to_agent_run_request(
        request,
        part_converter,
    )

    if run_request.run_config is None:
        run_request.run_config = RunConfig()

    run_request.run_config.streaming_mode = StreamingMode.SSE

    return run_request


def create_a2a_app(
    agent: LlmAgent,
    config: Config,
) -> Starlette:
    adk_logger = logging.getLogger("google_adk")
    adk_logger.setLevel(logging.INFO)

    async def create_runner() -> Runner:
        return Runner(
            app_name=agent.name,
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
            credential_service=InMemoryCredentialService(),
        )

    task_store = InMemoryTaskStore()
    push_config_store = InMemoryPushNotificationConfigStore()

    agent_executor = A2aAgentExecutor(
        runner=create_runner,
        config=A2aAgentExecutorConfig(request_converter=request_converter),
        use_legacy=False,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        push_config_store=push_config_store,
    )

    rpc_url = f"http://{config.server.listen_address}:{config.server.listen_port}"

    app = Starlette()

    async def setup_a2a():
        if isinstance(config.auth, ApiKeyAuthConfig):
            security_schemes = {
                "APIKeySecurityScheme": SecurityScheme(
                    APIKeySecurityScheme(
                        in_=In.header,
                        name=ApiKeyAuthMiddleware.HEADER_NAME,
                    )
                ),
            }
        elif isinstance(config.auth, OAuthConfig):
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
                            str(config.auth.issuer_url), external=True
                        ),
                    )
                ),
            }
        else:
            security = None
            security_schemes = None

        agent_description = agent.description
        if isinstance(agent.instruction, str):
            agent_description += f"\n{agent.instruction}"

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
                    description=agent_description,
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

    app.add_event_handler("startup", setup_a2a)
    return app


def create_app(config: Config) -> Starlette:
    root_agent = LlmAgent(
        model=LiteLlm(
            model=f"openai/{config.llm.model}",
            api_base=str(config.llm.api_url),
            api_key=config.llm.api_key.get_secret_value(),
        ),
        name=config.agent.name,
        description=config.agent.description,
        instruction=config.agent.instructions,
        tools=get_mcp_tool_set(config.mcp_servers),
    )

    app = create_a2a_app(root_agent, config)

    if isinstance(config.auth, ApiKeyAuthConfig):
        logger.info("Auth mode: API Key")
        app.add_middleware(
            ApiKeyAuthMiddleware,
            api_key=config.auth.api_key.get_secret_value(),
        )
    elif isinstance(config.auth, OAuthConfig):
        logger.info("Auth mode: OAuth2")

        app.add_middleware(
            OAuth2BearerAuthMiddleware,
            issuer_url=str(config.auth.issuer_url),
            realm=root_agent.name,
            config=config.auth.policies,
        )
    else:
        logger.info("Auth disabled.")

    return app
