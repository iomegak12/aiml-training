"""Persistent Chroma vector databases accessed through LangChain's ``Chroma`` wrapper.

Each store lives in its own persist directory (a separate database) with one collection
that uses cosine distance, the usual choice for OpenAI embeddings. The collection's
metadata records how it was built (embedding model, chunk settings, ...), which makes
every database self-describing for the validation script.

Writes use pre-computed embeddings so that the pipeline controls batching and
parallelism; reads and similarity search go through the normal LangChain API.
"""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from data_ingestion.config import StoreConfig

COSINE = {"hnsw": {"space": "cosine"}}


def open_store(cfg: StoreConfig, embeddings: Embeddings | None = None) -> Chroma:
    """Open (or create) the persistent Chroma collection for ``cfg``.

    ``embeddings`` is only needed for similarity search; read-only inspection works without it.
    """
    cfg.persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=cfg.collection_name,
        embedding_function=embeddings,
        persist_directory=str(cfg.persist_dir),
        collection_configuration=COSINE,
    )


def reset_store(store: Chroma) -> None:
    """Delete every record and the collection metadata, leaving an empty collection."""
    store.reset_collection()


def record_count(store: Chroma) -> int:
    """Number of records (chunks) in the collection."""
    return store._collection.count()  # noqa: SLF001 - langchain_chroma exposes no public count()


def collection_metadata(store: Chroma) -> dict:
    """Build information stored on the collection (empty for a new collection)."""
    return dict(store._collection.metadata or {})  # noqa: SLF001


def write_collection_metadata(store: Chroma, metadata: dict) -> None:
    """Replace the collection metadata with ``metadata`` (scalar values only)."""
    store._collection.modify(metadata=metadata)  # noqa: SLF001


def existing_fingerprints(store: Chroma) -> dict[str, dict[str, str]]:
    """Map ``doc_id -> {chunk_id: content_hash}`` for everything already in the store."""
    data = store.get(include=["metadatas"])
    fingerprints: dict[str, dict[str, str]] = {}
    for chunk_id, meta in zip(data["ids"], data["metadatas"], strict=True):
        meta = meta or {}
        fingerprints.setdefault(meta.get("doc_id", "?"), {})[chunk_id] = meta.get("content_hash", "")
    return fingerprints


def delete_document(store: Chroma, doc_id: str) -> None:
    """Remove all chunks of ``doc_id`` from the store."""
    store._collection.delete(where={"doc_id": doc_id})  # noqa: SLF001


def upsert_chunks(store: Chroma, ids: list[str], texts: list[str], metadatas: list[dict],
                  vectors: list[list[float]], batch_size: int) -> None:
    """Write chunks with pre-computed embeddings in batches of ``batch_size`` (insert or overwrite by ID)."""
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        store._collection.upsert(  # noqa: SLF001
            ids=ids[start:end], documents=texts[start:end], metadatas=metadatas[start:end],
            embeddings=vectors[start:end],
        )
