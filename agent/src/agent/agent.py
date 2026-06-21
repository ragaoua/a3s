from langchain.agents import AgentState, create_agent
from langchain.agents.middleware.types import (
    InputAgentState,
    OutputAgentState,
    ResponseT,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.typing import ContextT

from src.config.types import AgentConfig, LlmConfig, McpServerConfig

LangChainAgent = CompiledStateGraph[
    AgentState[ResponseT], ContextT, InputAgentState, OutputAgentState[ResponseT]
]


def build_agent(
    *,
    llm_config: LlmConfig,
    agent_config: AgentConfig,
    mcp_servers_config: list[McpServerConfig],
) -> LangChainAgent:
    model = ChatOpenAI(
        model=llm_config.model,
        base_url=str(llm_config.api_url),
        api_key=llm_config.api_key,
    )

    # TODO: langchain-migration - wire MCP, skills, and subagent tools. These
    # remain ADK-coupled and are handled in a follow-up; the core loop runs
    # tool-less for now.
    tools = []

    return create_agent(
        model,
        tools,
        system_prompt=agent_config.instructions,
        name=agent_config.name,
        checkpointer=InMemorySaver(),
    )
