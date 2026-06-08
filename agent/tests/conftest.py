from collections.abc import Iterator
import pytest
from pytest_httpserver import HTTPServer

from tests.common.llm import LlmFixture


MODEL_NAME = "mock-model"
API_KEY = "mock-api-key"


@pytest.fixture
def mock_llm(httpserver: HTTPServer) -> Iterator[LlmFixture]:
    yield LlmFixture(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key=API_KEY,
        model=MODEL_NAME,
        _server=httpserver,
    )
    httpserver.check_assertions()
