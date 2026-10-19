"""The four RAG pipelines wrapped as tools for the HR Policy and Product Manuals agents.

Each tool runs a synchronous pipeline in a worker thread (``asyncio.to_thread``), so
several specialists can search in parallel without blocking the event loop. Tool results
are compact JSON (answer, sources with quotes, trace) to keep the agent's context small.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from agentic_rag.config import AgentSettings
from agentic_rag.rag import advanced_rag, corrective_rag, hybrid_rag, multi_query_rag
from agentic_rag.rag.result import RagResult
from agentic_rag.retrieval.models import MetadataFilter
from agentic_rag.retrieval.stores import StoreKey


class SearchArgs(BaseModel):
    """Arguments shared by every RAG tool."""

    query: str = Field(description="The question or search text; keep codes, models and policy names verbatim")
    brand: str | None = Field(default=None, description="Brand filter, e.g. 'Voltara' (products only)")
    model: str | None = Field(default=None, description="Exact product model filter, e.g. 'Lumina 55 Pro'")
    include_superseded: bool = Field(default=False,
                                     description="HR only: also search superseded policy versions")


TOOL_DOCS = {
    "hybrid_search": "Fast keyword (BM25) + semantic search fused with RRF. Returns ranked passages WITHOUT an answer. "
                     "Best for error codes, model numbers, policy IDs and exact terms.",
    "advanced_search": "Rewrites the query, searches (current versions only), reranks with an LLM and drafts a cited "
                       "answer. Best default for most questions.",
    "multi_query_search": "Splits a compound question into sub-questions, searches each separately, fuses the results "
                          "and drafts a cited answer. Use when the question asks several things.",
    "corrective_search": "Grades the evidence, broadens or switches source when it is weak, says 'I don't know' when "
                         "nothing is relevant, and checks the answer is grounded. Use when unsure the documents cover it.",
}


def _filter(args: SearchArgs) -> MetadataFilter | None:
    """Metadata filter from the tool arguments (``None`` lets the pipeline infer one)."""
    flt = MetadataFilter(brand=args.brand, model=args.model)
    return None if flt.is_empty() else flt


def make_rag_tools(settings: AgentSettings, store: StoreKey) -> list[BaseTool]:
    """Create ``hybrid_search``, ``advanced_search``, ``multi_query_search`` and ``corrective_search`` for ``store``."""

    def runner(name: str) -> Callable[..., object]:
        """Build the async implementation of tool ``name``."""

        async def run(query: str, brand: str | None = None, model: str | None = None,
                      include_superseded: bool = False) -> str:
            args = SearchArgs(query=query, brand=brand, model=model, include_superseded=include_superseded)
            flt = _filter(args)

            def call() -> RagResult:
                if name == "hybrid_search":
                    return hybrid_rag(settings, store, query, flt=flt, generate=False)
                if name == "advanced_search":
                    return advanced_rag(settings, store, query, flt=flt, include_superseded=include_superseded or None)
                if name == "multi_query_search":
                    return multi_query_rag(settings, store, query, flt=flt, include_superseded=include_superseded)
                return corrective_rag(settings, store, query, flt=flt, include_superseded=include_superseded or None)

            try:
                return (await asyncio.to_thread(call)).to_tool_output()
            except Exception as exc:  # noqa: BLE001 - report the failure to the agent instead of crashing it
                return f'{{"error": "{type(exc).__name__}: {str(exc)[:200]}"}}'

        return run

    return [StructuredTool.from_function(coroutine=runner(name), name=name, description=doc, args_schema=SearchArgs)
            for name, doc in TOOL_DOCS.items()]
