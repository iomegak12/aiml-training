"""Pipeline 1 - hybrid RAG: metadata filter + (vector and BM25 fused with RRF) -> context -> answer.

No LLM calls before retrieval, so it is the fastest pipeline. A product model or policy ID
named in the question becomes a metadata filter automatically (``infer_filter``).
"""

from __future__ import annotations

from agentic_rag.config import AgentSettings
from agentic_rag.rag.answer import compose_result
from agentic_rag.rag.result import RagResult
from agentic_rag.retrieval.filters import infer_filter, normalise_filter
from agentic_rag.retrieval.hybrid import add_current_version, hybrid_search
from agentic_rag.retrieval.models import MetadataFilter
from agentic_rag.retrieval.stores import StoreKey


def hybrid_rag(settings: AgentSettings, store: StoreKey, question: str, *, flt: MetadataFilter | None = None,
               k: int | None = None, use_mmr: bool = False, generate: bool = True) -> RagResult:
    """Answer ``question`` from ``store`` with hybrid retrieval.

    Args:
        settings: Agent settings.
        store: ``hr`` or ``products``.
        question: User question.
        flt: Explicit metadata filter; inferred from the question when omitted.
        k: Passages in the context (default ``RAG_TOP_K``).
        use_mmr: Diversify the dense side with MMR.
        generate: False returns retrieval only (no answer LLM call).
    """
    k = k or settings.rag_top_k
    flt = normalise_filter(settings, store, flt) if flt is not None else infer_filter(settings, store, question)
    trace = [f"filter: {flt.constraints() or 'none'}"]
    chunks = hybrid_search(settings, store, question, k=k, flt=flt, use_mmr=use_mmr)
    if not chunks and not flt.is_empty():
        trace.append("no hits with filter -> retried without filter")
        flt = MetadataFilter()
        chunks = hybrid_search(settings, store, question, k=k, use_mmr=use_mmr)
    trace.append(f"hybrid ({'mmr' if use_mmr else 'similarity'} + bm25, RRF): {len(chunks)} chunks "
                 f"from {', '.join(dict.fromkeys(c.doc_id for c in chunks)) or 'nothing'}")
    chunks, note = add_current_version(settings, store, question, flt, chunks)
    if note:
        trace.append(note)
    return compose_result(settings, "hybrid", store, question, chunks, trace, flt, generate)
