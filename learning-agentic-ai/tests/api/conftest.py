import json
import logging
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from helpers import ScriptedModel

from api import create_app
from api.config import ApiSettings
from api.logging_setup import APP_LOGGER
from api.rate_limit import RateLimiter
from api.runtime import AgentRuntime
from ticket_agent import AgentSettings, build_agent, build_planning_agent
from ticket_agent import settings as agent_settings_module


@pytest.fixture(autouse=True)
def agent_env(monkeypatch):
    """Valid agent settings from the environment only (the developer's .env is ignored)."""
    monkeypatch.setattr(agent_settings_module, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.1")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


@pytest.fixture
def log_dir(tmp_path):
    yield tmp_path / "logs"
    for handler in list(logging.getLogger(APP_LOGGER).handlers):
        logging.getLogger(APP_LOGGER).removeHandler(handler)
        handler.close()


@pytest.fixture
def make_runtime(service) -> Callable[..., AgentRuntime]:
    def factory(chat: list | None = None, plan: list | None = None) -> AgentRuntime:
        return AgentRuntime(
            agent=build_agent(model=ScriptedModel(responses=chat or []), ticket_service=service),
            planner=build_planning_agent(model=ScriptedModel(responses=plan or []), ticket_service=service),
            ticket_service=service,
            settings=AgentSettings(model="gpt-5.1", reasoning_effort="high"),
        )

    return factory


@pytest.fixture
def make_client(log_dir) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(runtime: AgentRuntime, rate_limiter: RateLimiter | None = None) -> TestClient:
        app = create_app(
            settings=ApiSettings(log_dir=log_dir),
            runtime=runtime,
            rate_limiter=rate_limiter,
            show_banner=False,
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def read_logs(log_dir) -> Callable[[], list[dict]]:
    def reader() -> list[dict]:
        for handler in logging.getLogger(APP_LOGGER).handlers:
            handler.flush()
        lines = (log_dir / "api.log").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    return reader

