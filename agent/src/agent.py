import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.apps.jsonrpc import DefaultCallContextBuilder
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.a2a.converters.request_converter import (
    AgentRunRequest,
    convert_a2a_request_to_agent_run_request,
)
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from starlette.applications import Starlette
from starlette.requests import Request

from .auth import ApiKeyAuthMiddleware, OAuth2BearerAuthMiddleware
from .config import APIKeyAuth, Config, OAuth2Auth, from_env
from .loggingManager import LoggingManager

logger = LoggingManager().get_logger(__name__)


def header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    authorization_header = ctx.state.get("authorization_header")
    if isinstance(authorization_header, str) and authorization_header:
        return {"Authorization": authorization_header}
    return {}


class MiddlewareCallContextBuilder(DefaultCallContextBuilder):
    def build(self, request: Request):
        context = super().build(request)

        authorization_header = getattr(request.state, "authorization_header", None)
        if isinstance(authorization_header, str) and authorization_header:
            context.state["authorization_header"] = authorization_header

        return context


def request_converter(
    request: RequestContext,
    part_converter,
) -> AgentRunRequest:
    run_request = convert_a2a_request_to_agent_run_request(
        request,
        part_converter,
    )

    call_context = request.call_context
    authorization_header = (
        call_context.state.get("authorization_header") if call_context else None
    )

    if isinstance(authorization_header, str) and authorization_header:
        run_request.state_delta = {
            **(run_request.state_delta or {}),
            "authorization_header": authorization_header,
        }

    return run_request


def create_a2a_app(
    agent: BaseAgent,
    *,
    host: str = "localhost",
    port: int = 8000,
    protocol: str = "http",
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
        config=A2aAgentExecutorConfig(
            request_converter=request_converter,
        ),
    )
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        push_config_store=push_config_store,
    )

    rpc_url = f"{protocol}://{host}:{port}"

    def create_static_agent_card() -> AgentCard:
        return AgentCard(
            name=agent.name,
            description=agent.description,
            url=rpc_url,
            version="0.0.1",
            capabilities=AgentCapabilities(),
            skills=[
                AgentSkill(
                    id=agent.name,
                    name="model" if isinstance(agent, LlmAgent) else "agent",
                    description=agent.description,
                    tags=["llm"] if isinstance(agent, LlmAgent) else ["custom_agent"],
                )
            ],
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            # TODO: maybe this is interesting.
            # We would provide an extended agent card to authorized users
            # to, for instance, be able to see what MCP tools the agent has
            # access to
            supports_authenticated_extended_card=False,
        )

    app = Starlette()

    async def setup_a2a():
        final_agent_card: AgentCard = create_static_agent_card()
        a2a_server = A2AStarletteApplication(
            agent_card=final_agent_card,
            http_handler=request_handler,
            context_builder=MiddlewareCallContextBuilder(),
        )
        a2a_server.add_routes_to_app(app)

    app.add_event_handler("startup", setup_a2a)
    return app


def create_app(config: Config) -> Starlette:
    root_agent = LlmAgent(
        model=LiteLlm(
            model=f"openai/{config.MODEL}",
            api_base=config.LLM_API_URI,
            api_key=config.LLM_API_KEY,
        ),
        name=config.AGENT_NAME,
        description=config.AGENT_DESCRIPTION,
        instruction=config.AGENT_INTRUCTIONS,
        tools=[
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(url=url),
                header_provider=header_provider,
            )
            for url in config.MCP_SERVERS
        ],
    )

    # NOTE: LISTEN_PORT is necessary here because that's the value that will be
    # used for the url for the agent's card. Since this is intended to be run
    # inside a container, and the port will be published, this a2a agent needs
    # to know on which port it will be exposed. We should probably do the same
    # for the host, but we're only working with localhost for now.
    app = create_a2a_app(root_agent, port=config.LISTEN_PORT)
    if isinstance(config.AUTH, APIKeyAuth):
        logger.info("Auth mode: API Key")
        app.add_middleware(ApiKeyAuthMiddleware, api_key=config.AUTH.api_key)
    elif isinstance(config.AUTH, OAuth2Auth):
        logger.info("Auth mode: OAuth2")
        app.add_middleware(
            OAuth2BearerAuthMiddleware,
            issuer_url=config.AUTH.oauth2_issuer_url,
            jwks_url=config.AUTH.oauth2_jwks_url,
            realm=root_agent.name,
        )
    else:
        logger.info("Auth disabled.")

    return app


def create_app_from_env() -> Starlette:
    return create_app(from_env())
