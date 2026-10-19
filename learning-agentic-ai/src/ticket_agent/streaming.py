"""Stream an agent run as typed events, or print them (reasoning, answer tokens, tool calls, tool results)."""

import json
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command, Interrupt

DIM, CYAN, YELLOW, RESET = "\033[2m", "\033[36m", "\033[33m", "\033[0m"
MAX_RESULT_CHARS = 400


def _is_subagent(namespace: tuple[str, ...]) -> bool:
    """True for events from a subagent spawned by the `task` tool."""
    return any(segment.startswith("tools:") for segment in namespace)


def _content_parts(message: AIMessage) -> list[tuple[str, str]]:
    """Split a streamed chunk into ("reasoning" | "text", text) parts."""
    if isinstance(message.content, str):
        return [("text", message.content)] if message.content else []

    parts = []
    for block in message.content:
        if isinstance(block, str):
            parts.append(("text", block))
        elif block.get("type") == "text" and block.get("text"):
            parts.append(("text", block["text"]))
        elif block.get("type") == "reasoning":
            for summary in block.get("summary", []):
                if summary.get("text"):
                    parts.append(("reasoning", summary["text"]))
            if block.get("reasoning"):  # standard (v1) reasoning block
                parts.append(("reasoning", block["reasoning"]))
    return parts


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + " ..."


class _Printer:
    """Prints streamed output, starting a new line whenever the kind of output changes."""

    def __init__(self) -> None:
        self._mode: str | None = None

    def stream_text(self, source: str, kind: str, text: str) -> None:
        if self._mode != kind:
            self._newline()
            label = f"{DIM}🧠 {source}thinking: " if kind == "reasoning" else f"🤖 {source}"
            print(label, end="")
            self._mode = kind
        print(text, end="", flush=True)
        if kind == "reasoning":
            print(RESET, end="")

    def line(self, text: str) -> None:
        self._newline()
        print(text, flush=True)

    def _newline(self) -> None:
        if self._mode is not None:
            print(RESET)
        self._mode = None

    def finish(self) -> None:
        self._newline()


def iter_agent_events(
    agent: Any, payload: str | dict | Command, config: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    """Run the agent and yield typed events as they stream.

    Event shapes (every event also has `subagent: bool`):
        {"type": "reasoning", "text": ...}   reasoning-summary text
        {"type": "token", "text": ...}       answer text
        {"type": "tool_call", "id": ..., "name": ..., "args": {...}}
        {"type": "tool_result", "tool_call_id": ..., "name": ..., "content": ...}

    Args:
        agent: A compiled deep agent (with a checkpointer).
        payload: A user message, an input dict, or a Command(resume=...).
        config: Thread config, e.g. ticket_agent.new_thread().
    """
    if isinstance(payload, str):
        payload = {"messages": [{"role": "user", "content": payload}]}

    for chunk in agent.stream(
        payload,
        config=config,
        stream_mode=["updates", "messages"],
        subgraphs=True,
        version="v2",
    ):
        subagent = _is_subagent(chunk["ns"])

        if chunk["type"] == "messages":
            message, _metadata = chunk["data"]
            if isinstance(message, AIMessage):  # chunks while streaming; a full message if the model didn't stream
                for kind, text in _content_parts(message):
                    yield {"type": "reasoning" if kind == "reasoning" else "token", "text": text, "subagent": subagent}

        elif chunk["type"] == "updates":
            for update in chunk["data"].values():
                if not isinstance(update, dict) or not isinstance(update.get("messages"), list):
                    continue
                for message in update["messages"]:
                    if isinstance(message, AIMessage):
                        for call in message.tool_calls:
                            yield {
                                "type": "tool_call",
                                "id": call.get("id"),
                                "name": call["name"],
                                "args": call["args"],
                                "subagent": subagent,
                            }
                    elif isinstance(message, ToolMessage):
                        yield {
                            "type": "tool_result",
                            "tool_call_id": message.tool_call_id,
                            "name": message.name,
                            "content": message.content,
                            "subagent": subagent,
                        }


def stream_agent(
    agent: Any, payload: str | dict | Command, config: dict[str, Any]
) -> tuple[Interrupt, ...]:
    """Run the agent with streaming output printed to the console / notebook.

    Args:
        agent: A compiled deep agent (with a checkpointer).
        payload: A user message, an input dict, or a Command(resume=...).
        config: Thread config, e.g. ticket_agent.new_thread().

    Returns:
        Pending interrupts (e.g. a plan waiting for approval); empty when the run finished.
    """
    printer = _Printer()
    for event in iter_agent_events(agent, payload, config):
        source = "[subagent] " if event["subagent"] else ""
        if event["type"] in ("reasoning", "token"):
            printer.stream_text(source, "reasoning" if event["type"] == "reasoning" else "text", event["text"])
        elif event["type"] == "tool_call":
            printer.line(f"{CYAN}🔧 {source}{event['name']}({_short(event['args'])}){RESET}")
        elif event["type"] == "tool_result":
            printer.line(f"{YELLOW}   ↳ {source}{event['name']}: {_short(event['content'])}{RESET}")

    printer.finish()
    return agent.get_state(config).interrupts
