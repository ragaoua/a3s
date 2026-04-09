from pydantic import Field, SecretStr
from pydantic_core import Url

from src.config.types.common import NonEmptyStr, StrictModel


class LlmConfig(StrictModel):
    api_url: Url
    api_key: SecretStr = Field(min_length=1)
    model: NonEmptyStr
