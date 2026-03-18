from pydantic_settings import SettingsConfigDict
from src.config import Config


def get_base_test_config_ignoring_env_file_with(
    *,
    LLM_API_URI: str = "endpoint",
    LLM_API_KEY: str = "fakekey",
    MODEL: str = "mymodel",
    AGENT_NAME: str = "Cody",
    AGENT_DESCRIPTION: str = "A helpful coding assistant",
    AGENT_INSTRUCTIONS: str = "You are a coding agent. Use the tools provided to access the user's requests regarding coding tasks",
    LISTEN_PORT: int = 12345,
    AGENT_API_KEY: str | None = None,
    OAUTH2_ISSUER_URL: str | None = None,
    OAUTH2_JWKS_URL: str | None = None,
    NO_AUTH: bool = False,
    MCP_SERVERS: list[str] | None = None,
) -> Config:
    # disable env file loading
    class TestConfig(Config):
        model_config = SettingsConfigDict(env_file=None)

    return TestConfig(
        LLM_API_URI=LLM_API_URI,
        LLM_API_KEY=LLM_API_KEY,
        MODEL=MODEL,
        AGENT_NAME=AGENT_NAME,
        AGENT_DESCRIPTION=AGENT_DESCRIPTION,
        AGENT_INSTRUCTIONS=AGENT_INSTRUCTIONS,
        LISTEN_PORT=LISTEN_PORT,
        AGENT_API_KEY=AGENT_API_KEY,
        OAUTH2_ISSUER_URL=OAUTH2_ISSUER_URL,
        OAUTH2_JWKS_URL=OAUTH2_JWKS_URL,
        NO_AUTH=NO_AUTH,
        MCP_SERVERS=list(MCP_SERVERS) if MCP_SERVERS is not None else [],
    )
