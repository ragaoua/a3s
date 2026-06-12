from dataclasses import dataclass
from typing import Any

from a2a.types import Task

from tests.common.llm import LlmFixture


@dataclass(frozen=True)
class A2aServerFixture:
    base_url: str
    mock_llm: LlmFixture


def get_adk_data_parts(task: Task, adk_type: str) -> list[dict[str, Any]]:
    return [
        part.root.data
        for artifact in (task.artifacts or [])
        for part in artifact.parts
        if part.root.kind == "data"
        and part.root.metadata is not None
        and part.root.metadata.get("adk_type") == adk_type
    ]
