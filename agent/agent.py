import os
import sys
from google.adk.agents import LlmAgent


from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm

for var in [
    "API_URI",
    "API_KEY",
    "AGENT_NAME",
    "AGENT_DESCRIPTION",
    "AGENT_INSTRUCTIONS",
    "LISTEN_PORT",
]:
    if var not in os.environ:
        print(f"Variable {var} not found")
        sys.exit(1)

root_agent = LlmAgent(
    model=LiteLlm(
        model="openai/C2-Cloud-Gemini-2.5-Flash",
        api_base=os.environ["API_URI"],
        api_key=os.environ["API_KEY"],
    ),
    name=os.environ["AGENT_NAME"],
    description=os.environ["AGENT_DESCRIPTION"],
    instruction=os.environ["AGENT_INSTRUCTIONS"],
    # tools=[
    #     MCPToolset(
    #         connection_params=StreamableHTTPConnectionParams(
    #             url=os.getenv("MCP_SERVER_URL", "http://localhost:8080/mcp")
    #         )
    #     )
    # ],
)

# TODO: check that LISTEN_PORT is a valid integer
a2a_app = to_a2a(root_agent, port=int(os.environ["LISTEN_PORT"]))

# NOTE: LISTEN_PORT is necessary here because that's the value that will be
# used for the url for the agent's card. Since this is intended to be run
# inside a container, and the port will be published, this a2a agent needs
# to know on which port it will be exposed. We should probably fo the same
# for the host, but we're only working with localhost for now.
