"""FastAPI dependencies."""

from fastapi import Request

from api.runtime import AgentRuntime


def get_runtime(request: Request) -> AgentRuntime:
    return request.app.state.runtime
