import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.apps.jsonrpc import DefaultCallContextBuilder
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.a2a.converters.request_converter import (
    AgentRunRequest,
    convert_a2a_request_to_agent_run_request,
)
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from google.adk.a2a.executor.config import A2aAgentExecutorConfig
from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
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
from .config import APIKeyAuth, get_config
from .loggingManager import LoggingManager

logger = LoggingManager().get_logger(__name__)


def header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    api_key = ctx.state.get("api_key")
    if isinstance(api_key, str) and api_key:
        return {"X-Api-Key": api_key}
    return {}


class MiddlewareCallContextBuilder(DefaultCallContextBuilder):
    def build(self, request: Request):
        context = super().build(request)

        api_key = getattr(request.state, "api_key", None)
        if isinstance(api_key, str) and api_key:
            context.state["api_key"] = api_key

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
    api_key = call_context.state.get("api_key") if call_context else None
    if isinstance(api_key, str) and api_key:
        run_request.state_delta = {
            **(run_request.state_delta or {}),
            "api_key": api_key,
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

    card_builder = AgentCardBuilder(
        agent=agent,
        rpc_url=f"{protocol}://{host}:{port}/",
    )

    app = Starlette()

    async def setup_a2a():
        final_agent_card: AgentCard = await card_builder.build()
        a2a_server = A2AStarletteApplication(
            agent_card=final_agent_card,
            http_handler=request_handler,
            context_builder=MiddlewareCallContextBuilder(),
        )
        a2a_server.add_routes_to_app(app)

    app.add_event_handler("startup", setup_a2a)
    return app


config = get_config()
root_agent = LlmAgent(
    model=LiteLlm(
        model=f"openai/{config.model}",
        api_base=config.llm_api_uri,
        api_key=config.llm_api_key,
    ),
    name=config.agent_name,
    description=config.agent_description,
    instruction=config.agent_instructions,
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=url),
            header_provider=header_provider,
        )
        for url in config.mcp_servers
    ],
)


# NOTE: LISTEN_PORT is necessary here because that's the value that will be
# used for the url for the agent's card. Since this is intended to be run
# inside a container, and the port will be published, this a2a agent needs
# to know on which port it will be exposed. We should probably do the same
# for the host, but we're only working with localhost for now.
a2a_app = create_a2a_app(root_agent, port=config.listen_port)
if isinstance(config.auth, APIKeyAuth):
    logger.info("Auth mode: API Key")
    a2a_app.add_middleware(ApiKeyAuthMiddleware, api_key=config.auth.api_key)
else:
    logger.info("Auth mode: OAuth2")
    a2a_app.add_middleware(
        OAuth2BearerAuthMiddleware,
        issuer_url=config.auth.oauth2_issuer_url,
        jwks_url=config.auth.oauth2_jwks_url,
        realm=root_agent.name,
    )
