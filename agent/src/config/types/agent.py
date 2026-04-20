from pydantic import Field
from pydantic_core import Url

from src.config.types.common import NonEmptyStr, StrictModel


class AgentConfig(StrictModel):
    name: NonEmptyStr
    description: NonEmptyStr
    instructions: NonEmptyStr
    subagents: dict[NonEmptyStr, Url] = Field(default_factory=dict)
    skills_dir: NonEmptyStr = "config/skills"
