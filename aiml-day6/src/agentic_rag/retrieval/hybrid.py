"""Hybrid retrieval: dense (similarity or MMR) + BM25, fused with Reciprocal Rank Fusion.

RRF score of a chunk = sum over retrievers of ``1 / (rrf_k + rank)``. It needs no score
calibration between retrievers, which is why it is the default fusion method for
hybrid search. A chunk found by both retrievers rises to the top.
"""

from __future__ import annotations

from collections.abc import Sequence

from agentic_rag.config import AgentSettings
from agentic_rag.retrieval.filters import current_successor, normalise_filter
from agentic_rag.retrieval.keyword import keyword_search
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk
from agentic_rag.retrieval.stores import StoreKey
from agentic_rag.retrieval.vector import mmr_search, similarity_search


def rrf_fuse(ranked_lists: Sequence[Sequence[RetrievedChunk]], rrf_k: int = 60,
             labels: Sequence[str] | None = None) -> list[RetrievedChunk]:
    """Fuse ranked lists with Reciprocal Rank Fusion; returns chunks by descending RRF score.

    ``labels`` name each list (default: the retriever of its first chunk) and are kept in
    ``RetrievedChunk.ranks`` so you can see which retriever found what.
    """
    fused: dict[str, RetrievedChunk] = {}
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for i, ranked in enumerate(ranked_lists):
        label = labels[i] if labels else (ranked[0].retriever if ranked else f"list{i}")
        for rank, chunk in enumerate(ranked, start=1):
            fused.setdefault(chunk.chunk_id, chunk)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            ranks.setdefault(chunk.chunk_id, {})[label] = rank
    ordered = sorted(fused, key=lambda cid: scores[cid], reverse=True)
    return [fused[cid].model_copy(update={"score": round(scores[cid], 5), "retriever": "hybrid",
                                          "ranks": ranks[cid]}) for cid in ordered]


def hybrid_search(settings: AgentSettings, key: StoreKey, query: str, k: int | None = None,
                  flt: MetadataFilter | None = None, candidate_k: int | None = None,
                  use_mmr: bool = False) -> list[RetrievedChunk]:
    """Hybrid search on store ``key``: dense + BM25 candidates fused with RRF, top ``k`` returned.

    Args:
        settings: Agent settings (``RAG_TOP_K``, ``RAG_CANDIDATE_K`` and ``RRF_K`` are the defaults).
        key: ``hr`` or ``products``.
        query: Search text.
        k: Results to return.
        flt: Optional metadata filter applied to *both* retrievers.
        candidate_k: Candidates taken from each retriever before fusion.
        use_mmr: Use MMR instead of plain similarity for the dense side (more diverse results).
    """
    k = k or settings.rag_top_k
    candidate_k = max(candidate_k or settings.rag_candidate_k, k)
    flt = normalise_filter(settings, key, flt)
    dense = (mmr_search(settings, key, query, candidate_k, flt=flt) if use_mmr
             else similarity_search(settings, key, query, candidate_k, flt))
    sparse = keyword_search(settings, key, query, candidate_k, flt)
    return rrf_fuse([dense, sparse], settings.rrf_k, labels=[dense[0].retriever if dense else "vector", "bm25"])[:k]


def add_current_version(settings: AgentSettings, key: StoreKey, query: str, flt: MetadataFilter | None,
                        chunks: list[RetrievedChunk], n: int = 2) -> tuple[list[RetrievedChunk], str | None]:
    """When ``flt`` pins a *superseded* document, append the top ``n`` chunks of its current version.

    A question about an old policy ("under Leave Policy v2.0 ...") is answered from that version, but the
    answer should also say what applies today - which needs evidence from the current version.
    """
    successor = current_successor(settings, key, flt.doc_id) if flt and flt.doc_id else None
    if not successor:
        return chunks, None
    note = f"CURRENT VERSION - replaces {flt.doc_id}"
    extra = [c.model_copy(update={"metadata": {**c.metadata, "note": note}})
             for c in hybrid_search(settings, key, query, k=n, flt=MetadataFilter(doc_id=successor))]
    return chunks + extra, f"version: added {len(extra)} chunks from current version {successor} for comparison"
