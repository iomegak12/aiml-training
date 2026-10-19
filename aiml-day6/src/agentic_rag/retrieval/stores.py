"""Access to the two persistent Chroma stores built by ``data_ingestion``.

Stores and the BM25 corpus are cached per process: opening Chroma and reading every
chunk for BM25 happens once, then every query reuses them.
"""

from __future__ import annotations

import threading
from typing import Literal

from langchain_chroma import Chroma

from agentic_rag.config import AgentSettings
from agentic_rag.retrieval.models import RetrievedChunk
from data_ingestion.embeddings import make_embeddings
from data_ingestion.validation import store_exists
from data_ingestion.vectorstore import open_store

StoreKey = Literal["hr", "products"]
STORE_KEYS: tuple[StoreKey, ...] = ("hr", "products")

_lock = threading.Lock()
_stores: dict[tuple[str, str], Chroma] = {}
_chunks: dict[tuple[str, str], list[RetrievedChunk]] = {}


def get_store(settings: AgentSettings, key: StoreKey) -> Chroma:
    """Open (once) and return the Chroma store ``key`` with the query embeddings attached."""
    cfg = settings.store(key)
    if not store_exists(cfg):
        raise FileNotFoundError(f"Vector store {key!r} not found at {cfg.persist_dir}. Run `make ingest` first.")
    cache_key = (str(cfg.persist_dir), cfg.collection_name)
    with _lock:
        if cache_key not in _stores:
            settings.require_openai()
            _stores[cache_key] = open_store(cfg, make_embeddings(settings.ingestion))
        return _stores[cache_key]


def load_all_chunks(settings: AgentSettings, key: StoreKey) -> list[RetrievedChunk]:
    """Every chunk of store ``key`` (text and metadata), read once and cached; feeds BM25 and filters."""
    cfg = settings.store(key)
    cache_key = (str(cfg.persist_dir), cfg.collection_name)
    if cache_key not in _chunks:
        data = get_store(settings, key).get(include=["documents", "metadatas"])
        _chunks[cache_key] = [
            RetrievedChunk(chunk_id=cid, doc_id=str((meta or {}).get("doc_id", "?")), text=text or "",
                           metadata=dict(meta or {}), retriever="bm25")
            for cid, text, meta in zip(data["ids"], data["documents"], data["metadatas"], strict=True)
        ]
    return _chunks[cache_key]
