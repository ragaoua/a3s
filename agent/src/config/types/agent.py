from src.config.types.common import NonEmptyStr, StrictModel


class AgentConfig(StrictModel):
    name: NonEmptyStr
    description: NonEmptyStr
    instructions: NonEmptyStr
