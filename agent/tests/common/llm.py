import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr
from pydantic_core import Url
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Request, Response

from src.config.types import LlmConfig

CHAT_COMPLETIONS_PATH = "/chat/completions"


@dataclass(frozen=True)
class LlmFixture:
    api_url: str
    api_key: str
    model: str
    _server: HTTPServer

    def llm_config(self) -> LlmConfig:
        return LlmConfig(
            api_url=Url(self.api_url),
            api_key=SecretStr(self.api_key),
            model=self.model,
        )

    def stub_response(self, content: str) -> None:
        """Stub a one-shot chat-completion that returns plain assistant text."""
        self._stub_oneshot_message(
            message={"role": "assistant", "content": content},
            finish_reason="stop",
        )

    def stub_tool_call(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        call_id: str = "call_0",
    ) -> None:
        """Stub a one-shot chat-completion that asks the agent to invoke a tool."""
        self._stub_oneshot_message(
            message={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            },
            finish_reason="tool_calls",
        )

    def _stub_oneshot_message(
        self,
        *,
        message: dict[str, Any],
        finish_reason: str,
    ) -> None:
        def _dispatch(request: Request) -> Response:
            payload: dict[str, Any] = request.get_json()  # pyright: ignore[reportAny]

            if bool(payload.get("stream")):
                return Response(
                    response=_sse_body(
                        message=message, finish_reason=finish_reason, model=self.model
                    ),
                    status=200,
                    content_type="text/event-stream",
                )
            return Response(
                response=json.dumps(
                    {
                        "id": f"chatcmpl-{uuid.uuid4().hex}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": self.model,
                        "choices": [
                            {
                                "index": 0,
                                "message": message,
                                "finish_reason": finish_reason,
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                    }
                ),
                status=200,
                content_type="application/json",
            )

        _ = self._server.expect_oneshot_request(
            CHAT_COMPLETIONS_PATH, method="POST"
        ).respond_with_handler(_dispatch)

    @property
    def requests(self) -> list[Request]:
        return [log[0] for log in self._server.log]


def _sse_body(
    *,
    message: dict[str, Any],
    finish_reason: str,
    model: str,
) -> str:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def _chunk(delta: dict[str, Any], fr: str | None = None) -> dict[str, Any]:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": fr}],
        }

    chunks: list[dict[str, Any]] = []
    tool_calls = message.get("tool_calls")
    if tool_calls:
        delta_tool_calls: list[dict[str, Any]] = []
        for i, tc in enumerate(tool_calls):
            delta_tool_calls.append(
                {
                    "index": i,
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
            )
        chunks.append(
            _chunk(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": delta_tool_calls,
                }
            )
        )
    elif message.get("content") is not None:
        chunks.append(_chunk({"role": "assistant", "content": message["content"]}))

    chunks.append(_chunk({}, fr=finish_reason))
    chunks.append(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }
    )

    lines: list[str] = []
    for c in chunks:
        lines.append(f"data: {json.dumps(c)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines)
