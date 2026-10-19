"""Dense retrieval over Chroma: similarity search and Maximal Marginal Relevance (MMR)."""

from __future__ import annotations

from langchain_core.documents import Document

from agentic_rag.config import AgentSettings
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk
from agentic_rag.retrieval.stores import StoreKey, get_store


def _to_chunk(doc: Document, score: float, retriever: str, rank: int) -> RetrievedChunk:
    """Convert a LangChain ``Document`` into a ``RetrievedChunk``."""
    meta = dict(doc.metadata or {})
    return RetrievedChunk(chunk_id=str(meta.get("chunk_id") or doc.id), doc_id=str(meta.get("doc_id", "?")),
                          text=doc.page_content, metadata=meta, score=round(float(score), 4),
                          retriever=retriever, ranks={retriever: rank})


def similarity_search(settings: AgentSettings, key: StoreKey, query: str, k: int,
                      flt: MetadataFilter | None = None) -> list[RetrievedChunk]:
    """Top-``k`` chunks by cosine relevance (0-1, higher is better), optionally filtered."""
    where = flt.to_chroma_where() if flt else None
    hits = get_store(settings, key).similarity_search_with_relevance_scores(query, k=k, filter=where)
    return [_to_chunk(doc, score, "vector", rank) for rank, (doc, score) in enumerate(hits, start=1)]


def mmr_search(settings: AgentSettings, key: StoreKey, query: str, k: int, fetch_k: int | None = None,
               lambda_mult: float = 0.5, flt: MetadataFilter | None = None) -> list[RetrievedChunk]:
    """Top-``k`` chunks balancing relevance and diversity (MMR); scores are rank-based."""
    where = flt.to_chroma_where() if flt else None
    docs = get_store(settings, key).max_marginal_relevance_search(
        query, k=k, fetch_k=fetch_k or max(k * 4, 20), lambda_mult=lambda_mult, filter=where)
    return [_to_chunk(doc, 1.0 / rank, "mmr", rank) for rank, doc in enumerate(docs, start=1)]
