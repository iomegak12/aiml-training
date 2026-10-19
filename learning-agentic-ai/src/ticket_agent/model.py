"""Chat model construction."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from ticket_agent.settings import AgentSettings


def build_model(settings: AgentSettings | None = None) -> BaseChatModel:
    """Create the OpenAI reasoning model configured in .env.

    Uses the Responses API with the configured reasoning effort and asks for
    reasoning summaries so the agent's thinking can be streamed.
    """
    settings = settings or AgentSettings.from_env()
    return init_chat_model(
        settings.model_id,
        use_responses_api=True,
        reasoning={"effort": settings.reasoning_effort, "summary": "auto"},
    )
