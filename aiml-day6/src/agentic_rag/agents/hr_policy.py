"""HR Policy agent: answers employee-policy questions from the ``hr`` vector store."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agentic_rag.agents.base import SpecialistSpec
from agentic_rag.agents.rag_tools import make_rag_tools
from agentic_rag.config import AgentSettings

SPEC = SpecialistSpec(
    name="hr_policy",
    title="HR Policy agent of Aranya Technologies",
    description="HR policies (leave, travel and expenses, medical insurance, conduct, POSH, WFH, IT security, "
                "privacy, attendance, appraisal, whistleblowing, anti-bribery, notice period). Current versions "
                "by default; flags superseded values.",
    skills=("hr-policies", "rag-answering"),
    system_prompt="""Answer HR policy questions from the company policy documents only.
Use the search tools on the HR policy store; prefer advanced_search, and follow the hr-policies skill for
choosing a tool and for the version rules (current version by default, flag superseded values).""",
)


def tools(settings: AgentSettings) -> list[BaseTool]:
    """The four RAG pipelines over the HR store."""
    return make_rag_tools(settings, "hr")
