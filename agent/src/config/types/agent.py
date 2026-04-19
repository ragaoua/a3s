from src.config.types.common import NonEmptyStr, StrictModel


class AgentConfig(StrictModel):
    name: NonEmptyStr
    description: NonEmptyStr
    instructions: NonEmptyStr
    skills_dir: NonEmptyStr = "config/skills"
