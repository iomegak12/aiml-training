"""Grounded answer generation from a ``ContextPack``, with an explicit "I don't know", and result assembly."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from agentic_rag.config import AgentSettings
from agentic_rag.llm import fast_llm, structured
from agentic_rag.rag.context import DEFAULT_CONTEXT_TOKENS, ContextPack, build_context
from agentic_rag.rag.result import RagResult
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk

I_DONT_KNOW = "I don't know - the available documents do not contain this information."

ANSWER_RULES = """Answer the question using ONLY the numbered sources below.
- Cite every fact with its source ID in square brackets, e.g. [S2].
- Use the exact model and the CURRENT policy version; if a SUPERSEDED source disagrees, say which value is current.
- If the question asks about an old/superseded version and the sources also contain the current version, give the
  old value AND the current value (e.g. "18 days under v2.0; the current v3.0 allows 21 days").
- If the sources do not contain the answer, set answerable=false and answer exactly: "{idk}"
- Be concise: lead with the direct answer, then supporting detail."""


class GroundedAnswer(BaseModel):
    """An answer with the source IDs it relies on."""

    answer: str
    citations: list[str] = Field(default_factory=list, description="Source IDs used, e.g. ['S1', 'S3']")
    answerable: bool = Field(default=True, description="False when the sources do not contain the answer")


def generate_answer(settings: AgentSettings, question: str, context: ContextPack, extra_rules: str = "") -> GroundedAnswer:
    """Answer ``question`` from ``context`` with citations, or return the standard "I don't know"."""
    if not context.sources:
        return GroundedAnswer(answer=I_DONT_KNOW, citations=[], answerable=False)
    prompt = (f"{ANSWER_RULES.format(idk=I_DONT_KNOW)}\n{extra_rules}\n\nSOURCES:\n{context.text}\n\n"
              f"QUESTION: {question}")
    result = structured(fast_llm(settings), GroundedAnswer).invoke(prompt)
    cited = set(result.citations) | set(re.findall(r"\[(S\d+)\]", result.answer))
    valid = [sid for sid, _ in context.sources if sid in cited]
    if not result.answerable:
        return GroundedAnswer(answer=I_DONT_KNOW, citations=[], answerable=False)
    return GroundedAnswer(answer=result.answer, citations=valid, answerable=True)


def compose_result(settings: AgentSettings, pipeline: str, store: str, question: str, chunks: list[RetrievedChunk],
                   trace: list[str], flt: MetadataFilter | None = None, generate: bool = True,
                   max_tokens: int = DEFAULT_CONTEXT_TOKENS) -> RagResult:
    """Pack ``chunks`` into a context, optionally generate the answer, and return a ``RagResult``."""
    context = build_context(chunks, max_tokens=max_tokens)
    trace.append(f"context: {len(context.sources)} sources, {context.tokens} tokens, {context.dropped} dropped")
    result = RagResult(pipeline=pipeline, store=store, question=question, chunks=chunks, trace=trace,
                       filters=flt.constraints() if flt else {}, sources=RagResult.sources_from(context),
                       context_tokens=context.tokens)
    if generate:
        answer = generate_answer(settings, question, context)
        result.answer, result.cited, result.answerable = answer.answer, answer.citations, answer.answerable
    return result
