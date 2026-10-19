"""Chat-model factories for the four roles in the system.

| Role          | Used by                                            | Default effort |
|---------------|----------------------------------------------------|----------------|
| coordinator   | plan, reflect and synthesize nodes of the graph     | high           |
| specialist    | the five specialist Deep Agents                     | low            |
| fast          | RAG steps (rewrite, grade, rerank), memory extraction | low          |
| judge         | the judge gate (own model and API key)              | low            |

All models use the OpenAI Responses API with a reasoning effort, so "how hard the
model thinks" is one ``.env`` value per role.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from agentic_rag.config import AgentSettings


def make_chat_model(model: str, effort: str, api_key: str, *, timeout: float = 240, max_retries: int = 3) -> ChatOpenAI:
    """Build a ``ChatOpenAI`` model on the Responses API with the given reasoning ``effort``."""
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        reasoning={"effort": effort},
        use_responses_api=True,
        timeout=timeout,
        max_retries=max_retries,
    )


def coordinator_llm(settings: AgentSettings) -> ChatOpenAI:
    """The Coordinator's model: ``OPENAI_MODEL`` at ``COORDINATOR_REASONING_EFFORT``."""
    return make_chat_model(settings.model, settings.coordinator_effort, settings.require_openai(), timeout=600)


def specialist_llm(settings: AgentSettings) -> ChatOpenAI:
    """The specialists' model: ``SPECIALIST_MODEL`` (default: the fast model) at ``SPECIALIST_REASONING_EFFORT``."""
    return make_chat_model(settings.specialist_model, settings.specialist_effort, settings.require_openai())


def fast_llm(settings: AgentSettings) -> ChatOpenAI:
    """The model for small RAG and memory steps: ``OPENAI_FAST_MODEL`` at ``OPENAI_FAST_REASONING_EFFORT``."""
    return make_chat_model(settings.fast_model, settings.fast_effort, settings.require_openai())


def judge_llm(settings: AgentSettings) -> ChatOpenAI:
    """The judge: ``JUDGE_OPENAI_MODEL`` with ``JUDGE_OPENAI_API_KEY`` at ``JUDGE_REASONING_EFFORT``."""
    if not settings.judge_api_key:
        raise RuntimeError("JUDGE_OPENAI_API_KEY (or OPENAI_API_KEY) is not set; the judge cannot run.")
    return make_chat_model(settings.judge_model, settings.judge_effort, settings.judge_api_key)


def structured[SchemaT: BaseModel](llm: BaseChatModel, schema: type[SchemaT]) -> Runnable[list[BaseMessage] | str, SchemaT]:
    """Wrap ``llm`` so that it returns an instance of the Pydantic ``schema``.

    Function calling is used (not strict JSON-schema mode) so optional fields with
    defaults work without rewriting every model for OpenAI's strict-schema rules.
    """
    return llm.with_structured_output(schema, method="function_calling")


def message_text(message: BaseMessage) -> str:
    """Plain text of a model reply (Responses API replies carry a list of content blocks)."""
    return message.text if isinstance(message.text, str) else str(message.content)
