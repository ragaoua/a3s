from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
