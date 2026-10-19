"""Shared test helpers: a scripted chat model that replaces OpenAI in tests, and an SSE parser."""

import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedModel(BaseChatModel):
    """Returns pre-defined AI messages in order, ignoring the input.

    A response that is an exception instance is raised instead of returned.
    """

    responses: list[Any]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, BaseException):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def todos(*items: tuple[str, str]) -> dict:
    return {"todos": [{"content": content, "status": status} for content, status in items]}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Parse a text/event-stream body into (event, data) pairs."""
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events
