"""The specialist team: builds every agent that can run and records why others cannot."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from agentic_rag.agents import customer_support, hr_policy, product_manuals, research, ticket_management
from agentic_rag.agents.base import SpecialistSpec, build_specialist
from agentic_rag.config import AgentSettings
from agentic_rag.mcp_client import CrmToolkit

SPECS: dict[str, SpecialistSpec] = {m.SPEC.name: m.SPEC for m in
                                    (hr_policy, product_manuals, customer_support, ticket_management, research)}


@dataclass
class Specialist:
    """A specialist with its compiled agent, or the reason it is unavailable."""

    spec: SpecialistSpec
    agent: CompiledStateGraph | None
    reason: str = ""

    @property
    def available(self) -> bool:
        """True when the agent was built and its dependencies are reachable."""
        return self.agent is not None


def specialist_tools(name: str, settings: AgentSettings, crm: CrmToolkit) -> list[BaseTool]:
    """The tools of specialist ``name``."""
    if name == "hr_policy":
        return hr_policy.tools(settings)
    if name == "product_manuals":
        return product_manuals.tools(settings)
    if name == "customer_support":
        return customer_support.tools(crm)
    if name == "ticket_management":
        return ticket_management.tools(crm)
    return research.tools(settings)


def build_team(settings: AgentSettings, crm: CrmToolkit) -> dict[str, Specialist]:
    """Build all five specialists; CRM agents need the MCP server, Research needs ``SERPER_API_KEY``."""
    team: dict[str, Specialist] = {}
    for name, spec in SPECS.items():
        if spec.requires == "crm" and not crm.available:
            team[name] = Specialist(spec, None, f"CRM MCP server unavailable ({crm.error})")
        elif spec.requires == "serper" and not settings.serper_api_key:
            team[name] = Specialist(spec, None, "SERPER_API_KEY is not set")
        else:
            team[name] = Specialist(spec, build_specialist(spec, settings, specialist_tools(name, settings, crm)))
    return team


def roster(team: dict[str, Specialist]) -> str:
    """Markdown list of the agents for the Coordinator's planning prompt (availability included)."""
    lines = []
    for name, member in team.items():
        status = "available" if member.available else f"UNAVAILABLE - {member.reason}"
        lines.append(f"- `{name}` ({status}): {member.spec.description}")
    return "\n".join(lines)
