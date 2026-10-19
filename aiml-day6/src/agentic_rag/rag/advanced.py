"""Pipeline 2 - advanced RAG: rewrite -> filtered hybrid retrieval -> LLM rerank -> ordered context -> answer.

1. **Rewrite**: the fast model turns the question into a standalone, keyword-rich query and
   extracts brand/model filters ("my TV" + history -> "Voltara Lumina 55 Pro HDMI ...").
2. **Retrieve**: hybrid search over ``RAG_CANDIDATE_K`` candidates; HR questions are limited
   to current policy versions unless the user asks about an old version.
3. **Rerank**: the fast model scores every candidate 0-10; the best ``RAG_TOP_K`` survive.
4. **Prepare context**: de-duplicate, keep within the token budget, reading order.
"""

from __future__ import annotations

from agentic_rag.config import AgentSettings
from agentic_rag.rag.answer import compose_result
from agentic_rag.rag.result import RagResult
from agentic_rag.rag.steps import llm_rerank, rewrite_query
from agentic_rag.retrieval.filters import asks_for_old_version, current_only, infer_filter, normalise_filter
from agentic_rag.retrieval.hybrid import add_current_version, hybrid_search
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk
from agentic_rag.retrieval.stores import StoreKey


def advanced_retrieve(
    settings: AgentSettings, store: StoreKey, question: str, *, flt: MetadataFilter | None = None,
    k: int | None = None, history: str = "", include_superseded: bool | None = None,
) -> tuple[list[RetrievedChunk], list[str], MetadataFilter]:
    """Rewrite, retrieve and rerank; returns ``(top chunks, trace, filter used)`` without generating.

    ``include_superseded=None`` lets the query rewrite decide whether old policy versions are wanted.
    """
    k = k or settings.rag_top_k
    rewrite = rewrite_query(settings, question, store, history)
    trace = [f"rewrite: {rewrite.query!r}"]
    if flt is None:
        inferred = infer_filter(settings, store, question)
        llm_filter = MetadataFilter(brand=rewrite.brand, model=rewrite.model, model_number=rewrite.model_number)
        # Explicit mentions win; a family filter (comparison) must not be narrowed by the LLM's single model.
        flt = inferred if not inferred.is_empty() else llm_filter
    flt = normalise_filter(settings, store, flt)
    old_versions = (rewrite.include_superseded or asks_for_old_version(question)) if include_superseded is None \
        else include_superseded
    if not old_versions and current_only(settings, store, flt) != flt:
        flt = current_only(settings, store, flt)
        trace.append("version: current policies only (no old version requested)")
    candidates = hybrid_search(settings, store, rewrite.query, k=settings.rag_candidate_k, flt=flt)
    if not candidates and not flt.is_empty():
        trace.append(f"no hits with filter {flt.constraints()} -> retried without filter")
        flt = MetadataFilter()
        candidates = hybrid_search(settings, store, rewrite.query, k=settings.rag_candidate_k)
    trace.append(f"hybrid candidates: {len(candidates)} (filter: {flt.constraints() or 'none'})")
    top = llm_rerank(settings, question, candidates, k)
    trace.append("rerank: " + ", ".join(f"{c.citation()}={c.score:g}" for c in top))
    top, note = add_current_version(settings, store, rewrite.query, flt, top)
    if note:
        trace.append(note)
    return top, trace, flt


def advanced_rag(settings: AgentSettings, store: StoreKey, question: str, *, flt: MetadataFilter | None = None,
                 k: int | None = None, history: str = "", include_superseded: bool | None = None,
                 generate: bool = True) -> RagResult:
    """Answer ``question`` from ``store`` with rewrite + hybrid retrieval + LLM rerank.

    Args:
        settings: Agent settings.
        store: ``hr`` or ``products``.
        question: User question.
        flt: Explicit metadata filter (otherwise taken from the rewrite and the question).
        k: Passages kept after reranking (default ``RAG_TOP_K``).
        history: Recent conversation, used to resolve follow-ups like "and for the Pro model?".
        include_superseded: Search old policy versions too (``None``: decided by the query rewrite).
        generate: False returns retrieval only.
    """
    top, trace, flt = advanced_retrieve(settings, store, question, flt=flt, k=k, history=history,
                                        include_superseded=include_superseded)
    return compose_result(settings, "advanced", store, question, top, trace, flt, generate)
