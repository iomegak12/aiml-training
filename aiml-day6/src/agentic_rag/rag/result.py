"""The common result type of every RAG pipeline, plus a compact form for agent tools."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from agentic_rag.rag.context import ContextPack
from agentic_rag.rag.steps import Groundedness
from agentic_rag.retrieval.models import RetrievedChunk


class SourceRef(BaseModel):
    """A source as reported to the caller: ID, citation, label and a short quote."""

    source_id: str
    chunk_id: str
    doc_id: str
    page: int | None
    label: str
    quote: str


class RagResult(BaseModel):
    """Outcome of one RAG pipeline run.

    Attributes:
        pipeline: ``hybrid``, ``advanced``, ``multi_query`` or ``corrective``.
        store: Store that answered (``hr`` or ``products``); corrective RAG may switch stores.
        question: Original question.
        answer: Generated answer with ``[S#]`` citations (empty when ``generate=False``).
        answerable: False when the pipeline concluded "I don't know".
        sources: Sources in the context, in prompt order.
        cited: Source IDs the answer cites.
        chunks: Ranked chunks before context packing (for evaluation, e.g. hit@k).
        trace: Human-readable log of each step (queries, filters, grades, switches).
        filters: Metadata filter applied, if any.
        groundedness: Statement-level support check (corrective RAG only).
        context_tokens: Size of the context sent to the model.
    """

    pipeline: str
    store: str
    question: str
    answer: str = ""
    answerable: bool = True
    sources: list[SourceRef] = Field(default_factory=list)
    cited: list[str] = Field(default_factory=list)
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    groundedness: Groundedness | None = None
    context_tokens: int = 0

    @staticmethod
    def sources_from(context: ContextPack, quote_chars: int = 2000) -> list[SourceRef]:
        """Convert a ``ContextPack`` into ``SourceRef`` objects (quote = whitespace-normalised chunk text)."""
        return [SourceRef(source_id=sid, chunk_id=c.chunk_id, doc_id=c.doc_id, page=c.page, label=c.label(),
                          quote=" ".join(c.text.split())[:quote_chars]) for sid, c in context.sources]

    def doc_ids(self) -> list[str]:
        """Distinct document IDs of the ranked chunks, best first."""
        return list(dict.fromkeys(c.doc_id for c in self.chunks))

    def to_tool_output(self, quote_chars: int | None = None) -> str:
        """Compact JSON for an agent tool result: answer, cited/available sources and the trace.

        Quotes default to 400 characters when an answer was generated, and to the full passage for
        retrieval-only results (the agent must read the passages itself, e.g. an error-code table row).
        """
        if quote_chars is None:
            quote_chars = 400 if self.answer else 2000
        payload = {
            "pipeline": self.pipeline,
            "store": self.store,
            "answerable": self.answerable,
            "answer": self.answer,
            "filters": self.filters,
            "sources": [{**s.model_dump(exclude={"chunk_id"}), "quote": s.quote[:quote_chars],
                         "cited": s.source_id in self.cited} for s in self.sources],
            "trace": self.trace,
        }
        if self.groundedness:
            payload["groundedness"] = self.groundedness.model_dump()
        return json.dumps(payload, ensure_ascii=False)
