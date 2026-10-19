"""Research agent: current, external information from the web through Serper."""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool

from agentic_rag.agents.base import SpecialistSpec
from agentic_rag.config import AgentSettings
from agentic_rag.web.serper import SerperError, aserper_search

SPEC = SpecialistSpec(
    name="research",
    title="Research agent (public web via Serper)",
    description="Current external information: market trends, recent launches, prices, standards and news, "
                "with URLs and dates. Never for internal policies, manuals or customer data.",
    skills=("web-research",),
    system_prompt="""Research the task on the public web with web_search and report facts with their URLs and dates.
Follow the web-research skill: focused queries, reputable sources, recency stated, uncertainty in gaps.""",
    requires="serper",
)


def tools(settings: AgentSettings) -> list[BaseTool]:
    """The ``web_search`` tool bound to ``SERPER_API_KEY``."""

    async def web_search(query: str, kind: Literal["search", "news"] = "search", time_range: str | None = None,
                         num: int | None = None) -> str:
        """Search the web (kind='search') or recent news (kind='news'). time_range: d, w, m or y for recency."""
        try:
            results = await aserper_search(query, settings.serper_api_key, num=num or settings.serper_results,
                                           kind=kind, time_range=time_range)
        except SerperError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps([r.model_dump() for r in results], ensure_ascii=False)

    return [StructuredTool.from_function(coroutine=web_search, name="web_search")]
