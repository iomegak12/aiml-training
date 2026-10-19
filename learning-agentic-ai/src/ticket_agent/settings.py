"""Agent settings loaded from the .env file / environment."""

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

MODEL_ENV_VAR = "OPENAI_MODEL"
REASONING_EFFORT_ENV_VAR = "OPENAI_REASONING_EFFORT"
API_KEY_ENV_VAR = "OPENAI_API_KEY"

# Reasoning effort levels accepted by OpenAI reasoning models (not every model supports all).
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


class AgentConfigurationError(ValueError):
    """Raised when required agent settings are missing or invalid."""


@dataclass(frozen=True)
class AgentSettings:
    model: str
    reasoning_effort: str

    @property
    def model_id(self) -> str:
        """`provider:model` string used by init_chat_model."""
        return f"openai:{self.model}"

    @classmethod
    def from_env(cls) -> "AgentSettings":
        """Read OPENAI_MODEL and OPENAI_REASONING_EFFORT from .env / the environment."""
        load_dotenv(find_dotenv(usecwd=True))

        model = os.getenv(MODEL_ENV_VAR, "").strip()
        effort = os.getenv(REASONING_EFFORT_ENV_VAR, "").strip().lower()

        missing = [
            name for name, value in ((MODEL_ENV_VAR, model), (REASONING_EFFORT_ENV_VAR, effort)) if not value
        ]
        if missing:
            raise AgentConfigurationError(f"Missing setting(s) in .env: {', '.join(missing)}")
        if effort not in REASONING_EFFORTS:
            raise AgentConfigurationError(
                f"{REASONING_EFFORT_ENV_VAR}='{effort}' is invalid; "
                f"expected one of: {', '.join(REASONING_EFFORTS)}"
            )
        return cls(model=model, reasoning_effort=effort)


def is_api_key_set() -> bool:
    """True when OPENAI_API_KEY is present (the value itself is never exposed)."""
    load_dotenv(find_dotenv(usecwd=True))
    return bool(os.getenv(API_KEY_ENV_VAR, "").strip())
