import logging

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

from .auth import ApiKeyAuthMiddleware, OAuth2BearerAuthMiddleware
from .config import APIKeyAuth, get_config

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

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
        MCPToolset(connection_params=StreamableHTTPConnectionParams(url=url))
        for url in config.mcp_servers
    ],
)


# NOTE: LISTEN_PORT is necessary here because that's the value that will be
# used for the url for the agent's card. Since this is intended to be run
# inside a container, and the port will be published, this a2a agent needs
# to know on which port it will be exposed. We should probably do the same
# for the host, but we're only working with localhost for now.
a2a_app = to_a2a(root_agent, port=config.listen_port)
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
