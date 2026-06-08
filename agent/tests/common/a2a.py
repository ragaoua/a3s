from dataclasses import dataclass

from tests.common.llm import LlmFixture


@dataclass(frozen=True)
class A2aServerFixture:
    base_url: str
    mock_llm: LlmFixture
