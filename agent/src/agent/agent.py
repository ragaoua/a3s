from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from src.agent.mcp import get_mcp_toolsets
from src.agent.skills import get_skills_toolset
from src.agent.subagents import get_subagents
from src.config.types import AgentConfig, LlmConfig, McpServerConfig


def build_agent(
    *,
    llm_config: LlmConfig,
    agent_config: AgentConfig,
    mcp_servers_config: list[McpServerConfig],
):
    skills_toolset = get_skills_toolset(agent_config.skills_dir)
    mcp_toolsets = get_mcp_toolsets(mcp_servers_config)
    delegate_subagents, peer_subagents = get_subagents(agent_config.subagents)

    return LlmAgent(
        model=LiteLlm(
            model=f"openai/{llm_config.model}",
            api_base=str(llm_config.api_url),
            api_key=llm_config.api_key.get_secret_value(),
        ),
        name=agent_config.name,
        description=agent_config.description,
        instruction=agent_config.instructions,
        sub_agents=delegate_subagents,
        tools=mcp_toolsets + skills_toolset + peer_subagents,
    )
