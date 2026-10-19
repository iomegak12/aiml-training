"""Product Manuals agent: troubleshooting and specifications from the ``products`` vector store."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agentic_rag.agents.base import SpecialistSpec
from agentic_rag.agents.rag_tools import make_rag_tools
from agentic_rag.config import AgentSettings

SPEC = SpecialistSpec(
    name="product_manuals",
    title="Product Manuals agent for Voltara and Lumenix TVs and Nexora and Zentrix phones",
    description="TV and phone user manuals: specifications, setup, error codes, troubleshooting steps, warranty "
                "and safety. Pins the exact model (near-duplicate manuals).",
    skills=("product-support", "rag-answering"),
    system_prompt="""Answer product questions and troubleshoot devices from the user manuals only.
Always pin the exact model (pass `model`/`brand` to the search tools) - manuals of one family are near-duplicates.
Use hybrid_search for error codes and model numbers; follow the product-support skill.""",
)


def tools(settings: AgentSettings) -> list[BaseTool]:
    """The four RAG pipelines over the product-manual store."""
    return make_rag_tools(settings, "products")
