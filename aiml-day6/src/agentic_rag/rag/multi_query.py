"""Pipeline 3 - multi-query RAG: decompose -> search each sub-question in parallel -> fuse -> answer.

A compound question ("How many casual leaves do I get, and can I carry them forward?")
retrieves poorly as one query because each half pulls different passages. Decomposing it,
searching every sub-question separately and fusing the lists with RRF gives each part of
the question its own evidence. The top hits of every sub-question are always kept, so no
part of the question is crowded out of the context.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from agentic_rag.config import AgentSettings
from agentic_rag.rag.answer import compose_result
from agentic_rag.rag.context import dedupe
from agentic_rag.rag.result import RagResult
from agentic_rag.rag.steps import decompose_question
from agentic_rag.retrieval.filters import asks_for_old_version, current_only, infer_filter
from agentic_rag.retrieval.hybrid import hybrid_search, rrf_fuse
from agentic_rag.retrieval.models import MetadataFilter
from agentic_rag.retrieval.stores import StoreKey

PER_QUESTION_GUARANTEE = 2


def multi_query_rag(settings: AgentSettings, store: StoreKey, question: str, *, flt: MetadataFilter | None = None,
                    k: int | None = None, max_questions: int = 4, include_superseded: bool = False,
                    generate: bool = True) -> RagResult:
    """Answer a compound ``question`` by decomposing it and searching each part separately.

    Args:
        settings: Agent settings.
        store: ``hr`` or ``products``.
        question: User question.
        flt: Metadata filter applied to every sub-question (otherwise inferred per sub-question).
        k: Base number of passages; the context grows by up to two per extra sub-question.
        max_questions: Upper bound on sub-questions.
        include_superseded: Also search superseded policy versions (default: current versions only).
        generate: False returns retrieval only.
    """
    k = k or settings.rag_top_k
    subs = decompose_question(settings, question, max_questions)
    trace = [f"decomposed into {len(subs)}: " + " | ".join(subs)]
    filters = [flt if flt is not None else infer_filter(settings, store, q) for q in subs]
    if not (include_superseded or asks_for_old_version(question)):
        filters = [current_only(settings, store, f) for f in filters]
    with ThreadPoolExecutor(max_workers=len(subs)) as pool:
        lists = list(pool.map(lambda qf: hybrid_search(settings, store, qf[0], k=k, flt=qf[1]),
                              zip(subs, filters, strict=True)))
    for q, f, hits in zip(subs, filters, lists, strict=True):
        trace.append(f"  {q!r} (filter {f.constraints() or 'none'}): {[c.citation() for c in hits[:3]]}")
    guaranteed = [c for hits in lists for c in hits[:PER_QUESTION_GUARANTEE]]
    fused = rrf_fuse(lists, settings.rrf_k, labels=[f"q{i}" for i in range(1, len(subs) + 1)])
    budget = k + PER_QUESTION_GUARANTEE * (len(subs) - 1)
    chunks = dedupe(guaranteed + fused)[:budget]
    trace.append(f"fused (RRF) and kept {len(chunks)} chunks (top {PER_QUESTION_GUARANTEE} per sub-question guaranteed)")
    used = MetadataFilter(**filters[0].constraints()) if len({str(f.constraints()) for f in filters}) == 1 else None
    return compose_result(settings, "multi_query", store, question, chunks, trace, used, generate)
