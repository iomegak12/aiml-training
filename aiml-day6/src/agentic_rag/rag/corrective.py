"""Pipeline 4 - corrective RAG (CRAG): grade the evidence, correct course, verify the answer.

1. Retrieve with the advanced pipeline (rewrite, filtered hybrid, rerank).
2. **Grade** every passage relevant / not relevant and keep only relevant ones.
3. Too little relevant evidence -> **correct**: retry with the original wording, no filters and
   diverse (MMR) retrieval; still nothing -> try the **other store** (a warranty question asked
   to HR may live in a product manual).
4. Nothing relevant anywhere -> **admit "I don't know"** instead of guessing.
5. Generate, then **check groundedness** statement by statement; unsupported statements are
   removed by one regeneration, and the final check is reported with the result.
"""

from __future__ import annotations

from agentic_rag.config import AgentSettings
from agentic_rag.rag.advanced import advanced_retrieve
from agentic_rag.rag.answer import I_DONT_KNOW, compose_result, generate_answer
from agentic_rag.rag.context import build_context
from agentic_rag.rag.result import RagResult
from agentic_rag.rag.steps import check_groundedness, grade_chunks
from agentic_rag.retrieval.hybrid import hybrid_search
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk
from agentic_rag.retrieval.stores import StoreKey

OTHER_STORE: dict[str, StoreKey] = {"hr": "products", "products": "hr"}


def _relevant(settings: AgentSettings, question: str, chunks: list[RetrievedChunk], trace: list[str],
              label: str) -> list[RetrievedChunk]:
    """Grade ``chunks`` and return the relevant ones, logging the verdict."""
    grades = grade_chunks(settings, question, chunks)
    kept = [c for c, g in zip(chunks, grades, strict=True) if g.relevant]
    trace.append(f"grade ({label}): {len(kept)}/{len(chunks)} relevant")
    return kept


def corrective_rag(settings: AgentSettings, store: StoreKey, question: str, *, flt: MetadataFilter | None = None,
                   k: int | None = None, min_relevant: int = 2, allow_store_switch: bool = True,
                   history: str = "", include_superseded: bool | None = None, generate: bool = True) -> RagResult:
    """Answer ``question`` with grading, corrective re-retrieval, "I don't know" and a groundedness check.

    Args:
        settings: Agent settings.
        store: Store to try first (``hr`` or ``products``).
        question: User question.
        flt: Optional metadata filter for the first retrieval.
        k: Passages per retrieval (default ``RAG_TOP_K``).
        min_relevant: Relevant passages needed before the pipeline stops correcting.
        allow_store_switch: Try the other vector store when the first one has nothing relevant.
        history: Recent conversation for the query rewrite.
        include_superseded: Search old policy versions too (``None``: decided by the query rewrite).
        generate: False stops after grading (no answer or groundedness check).
    """
    k = k or settings.rag_top_k
    top, trace, used_filter = advanced_retrieve(settings, store, question, flt=flt, k=k, history=history,
                                                include_superseded=include_superseded)
    relevant = _relevant(settings, question, top, trace, "first pass")
    answered_from = store

    if len(relevant) < min_relevant:
        trace.append("correct: too little relevant evidence -> original wording, no filters, MMR retrieval")
        retry = hybrid_search(settings, store, question, k=k, use_mmr=True)
        fresh = [c for c in retry if c.chunk_id not in {r.chunk_id for r in relevant}]
        relevant += _relevant(settings, question, fresh, trace, "broadened")
        used_filter = MetadataFilter()

    if not relevant and allow_store_switch:
        other = OTHER_STORE[store]
        trace.append(f"correct: nothing relevant in {store!r} -> trying the {other!r} store")
        relevant = _relevant(settings, question, hybrid_search(settings, other, question, k=k), trace, other)
        if relevant:
            answered_from = other

    if not relevant:
        trace.append("no relevant evidence anywhere -> answer 'I don't know'")
        result = RagResult(pipeline="corrective", store=store, question=question, trace=trace,
                           answer=I_DONT_KNOW if generate else "", answerable=False)
        return result

    result = compose_result(settings, "corrective", answered_from, question, relevant, trace, used_filter,
                            generate=False)
    if not generate:
        return result

    context = build_context(relevant)
    answer = generate_answer(settings, question, context)
    check = check_groundedness(settings, answer.answer, context.text) if answer.answerable else None
    if check and not check.grounded:
        trace.append(f"groundedness {check.score}/100 -> regenerating without: {check.unsupported_statements}")
        rule = "Do NOT include these unsupported statements: " + "; ".join(check.unsupported_statements)
        answer = generate_answer(settings, question, context, extra_rules=rule)
        check = check_groundedness(settings, answer.answer, context.text) if answer.answerable else None
    if check:
        trace.append(f"groundedness check: {check.score}/100 ({'grounded' if check.grounded else 'NOT fully grounded'})")
    result.answer, result.cited, result.answerable, result.groundedness = (
        answer.answer, answer.citations, answer.answerable, check)
    return result
