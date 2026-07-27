from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, StringConstraints


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# A lowercase, hex-encoded SHA-256 digest (64 hex characters), as produced by
# `hashlib.sha256(...).hexdigest()`. Used to store API keys as a hash rather
# than plaintext, so a leaked config yields no usable credential.
Sha256Hex = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9a-f]{64}$")
]


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
