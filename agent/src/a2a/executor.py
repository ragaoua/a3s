from typing import override
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus, TextPart
from a2a.utils import new_agent_text_message
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.graph.state import RunnableConfig

from src.agent import LangChainAgent
from src.observability.logging import get_logger

logger = get_logger(__name__)


class LangGraphAgentExecutor(AgentExecutor):
    """Drives a compiled LangGraph agent in response to A2A requests."""

    def __init__(self, agent: LangChainAgent):
        self._agent = agent

    @override
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # The request handler guarantees task_id/context_id and validates that
        # any Task event carries the same task_id, so build it from the
        # context rather than minting fresh IDs.
        task = context.current_task
        if task is None:
            # task_id/context_id/message are typed Optional because RequestContext
            # can be built without a request, but the default request handler
            # always passes one (generating IDs if absent), so they're non-None
            # here. Assert to narrow the types and document the invariant.
            assert context.task_id is not None
            assert context.context_id is not None
            assert context.message is not None

            task = Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.submitted),
                history=[context.message],
            )
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        artifact_id = str(uuid4())

        try:
            append = False
            # Map the A2A conversation onto a LangGraph checkpointer thread so
            # multi-turn context is preserved.
            config = RunnableConfig(configurable={"thread_id": task.context_id})
            async for chunk, _metadata in self._agent.astream(
                {"messages": [HumanMessage(content=context.get_user_input())]},
                config=config,
                stream_mode="messages",
            ):
                # NOTE: we're only forwarding assistant token chunks.
                # tool/system messages and empty tool-call deltas aren't surfaced.
                # Should they ?
                if not isinstance(chunk, AIMessageChunk):
                    continue
                text = _chunk_text(chunk)
                if not text:
                    continue

                await updater.add_artifact(
                    [Part(root=TextPart(text=text))],
                    artifact_id=artifact_id,
                    name="response",
                    append=append,
                    last_chunk=(chunk.chunk_position == "last"),
                )
                append = True

            await updater.complete()
        except Exception as error:
            logger.exception("Agent execution failed")
            await updater.failed(
                message=new_agent_text_message(str(error), task.context_id, task.id)
            )

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # LangGraph has no native mid-run cancel hook; dropping the astream
        # iterator on disconnect is the practical mechanism. Revisit if/when
        # long-running/interruptible tasks are needed.
        raise NotImplementedError("Cancellation is not supported yet")


def _chunk_text(chunk: AIMessageChunk) -> str:
    """Extract plain text from a streamed chunk.

    Chunk content is a string for simple models but can be a list of content
    blocks for richer providers; concatenate the text blocks in that case.
    """
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""
