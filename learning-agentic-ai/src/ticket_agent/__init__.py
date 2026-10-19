"""IT support deep agent: settings, model, agent builders, streaming and plan approval."""

from ticket_agent.agent import build_agent, build_planning_agent, build_tools, new_thread
from ticket_agent.model import build_model
from ticket_agent.plan_approval import run_with_plan_approval
from ticket_agent.settings import AgentConfigurationError, AgentSettings, is_api_key_set
from ticket_agent.streaming import iter_agent_events, stream_agent

__all__ = [
    "AgentConfigurationError",
    "AgentSettings",
    "build_agent",
    "build_model",
    "build_planning_agent",
    "build_tools",
    "is_api_key_set",
    "iter_agent_events",
    "new_thread",
    "run_with_plan_approval",
    "stream_agent",
]
