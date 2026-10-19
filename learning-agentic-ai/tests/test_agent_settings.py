import pytest

from ticket_agent import settings as settings_module
from ticket_agent import AgentConfigurationError, AgentSettings, build_model, is_api_key_set


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    # Ignore the developer's real .env so tests only see what they set.
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: None)
    for name in ("OPENAI_MODEL", "OPENAI_REASONING_EFFORT", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", " HIGH ")
    settings = AgentSettings.from_env()
    assert settings == AgentSettings(model="gpt-5.1", reasoning_effort="high")
    assert settings.model_id == "openai:gpt-5.1"


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({}, "OPENAI_MODEL, OPENAI_REASONING_EFFORT"),
        ({"OPENAI_MODEL": "gpt-5.1"}, "OPENAI_REASONING_EFFORT"),
        ({"OPENAI_REASONING_EFFORT": "high"}, "OPENAI_MODEL"),
    ],
)
def test_missing_settings(monkeypatch, env, missing):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(AgentConfigurationError, match=missing):
        AgentSettings.from_env()


def test_invalid_reasoning_effort(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "extreme")
    with pytest.raises(AgentConfigurationError, match="invalid"):
        AgentSettings.from_env()


def test_is_api_key_set(monkeypatch):
    assert not is_api_key_set()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert is_api_key_set()


def test_build_model_uses_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")  # construction only, no API call
    model = build_model(AgentSettings(model="gpt-5.1", reasoning_effort="high"))
    assert model.model_name == "gpt-5.1"
    assert model.use_responses_api is True
    assert model.reasoning == {"effort": "high", "summary": "auto"}
