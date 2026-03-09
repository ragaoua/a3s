import os
import sys
from hmac import compare_digest

from google.adk.agents import LlmAgent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams


def _load_mcp_servers() -> list[str]:
    raw = os.getenv("MCP_SERVERS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]

    return []


for var in [
    "LLM_API_URI",
    "LLM_API_KEY",
    "AGENT_API_KEY",
    "MODEL",
    "AGENT_NAME",
    "AGENT_DESCRIPTION",
    "AGENT_INSTRUCTIONS",
    "LISTEN_PORT",
]:
    if var not in os.environ:
        print(f"Variable {var} not found")
        sys.exit(1)

mcp_servers = _load_mcp_servers()

model = os.environ["MODEL"]
root_agent = LlmAgent(
    model=LiteLlm(
        model=f"openai/{model}",
        api_base=os.environ["LLM_API_URI"],
        api_key=os.environ["LLM_API_KEY"],
    ),
    name=os.environ["AGENT_NAME"],
    description=os.environ["AGENT_DESCRIPTION"],
    instruction=os.environ["AGENT_INSTRUCTIONS"],
    tools=[
        MCPToolset(connection_params=StreamableHTTPConnectionParams(url=url))
        for url in mcp_servers
    ],
)


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        received_key = request.headers.get("API-Key", "")
        if not compare_digest(received_key, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "API-Key"},
            )

        return await call_next(request)


# TODO: check that LISTEN_PORT is a valid integer
a2a_app = to_a2a(root_agent, port=int(os.environ["LISTEN_PORT"]))
a2a_app.add_middleware(ApiKeyAuthMiddleware, api_key=os.environ["AGENT_API_KEY"])

# NOTE: LISTEN_PORT is necessary here because that's the value that will be
# used for the url for the agent's card. Since this is intended to be run
# inside a container, and the port will be published, this a2a agent needs
# to know on which port it will be exposed. We should probably fo the same
# for the host, but we're only working with localhost for now.
