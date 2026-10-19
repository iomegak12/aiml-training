"""Data types shared by every retriever: a retrieved chunk and a metadata filter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Chunk metadata keys that a filter may constrain (all written by data_ingestion).
FILTERABLE_FIELDS = ("doc_id", "brand", "model", "model_number", "family", "subcategory",
                     "status", "version", "section_title", "content_type")


class RetrievedChunk(BaseModel):
    """One chunk returned by a retriever.

    Attributes:
        chunk_id: Stable ID, e.g. ``TV-VOL-L55P:p004:c02``.
        doc_id: Source document ID, e.g. ``TV-VOL-L55P`` or ``HR-POL-001-V3.0``.
        text: Chunk text.
        metadata: Full Chroma metadata written by the ingestion pipeline.
        score: Retriever-specific score (cosine relevance, BM25, RRF or rerank); higher is better.
        retriever: Which retriever produced the score (``vector``, ``mmr``, ``bm25``, ``hybrid``, ``rerank``).
        ranks: 1-based rank of the chunk in each retriever that found it (filled by fusion).
    """

    chunk_id: str
    doc_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    retriever: str = "vector"
    ranks: dict[str, int] = Field(default_factory=dict)

    @property
    def page(self) -> int | None:
        """1-based page number of the chunk in its PDF."""
        page = self.metadata.get("page_number")
        return int(page) if page is not None else None

    @property
    def title(self) -> str:
        """Document title, e.g. ``Leave Policy`` or ``Voltara Lumina 55 Pro User Manual``."""
        return str(self.metadata.get("title") or self.doc_id)

    def citation(self) -> str:
        """Short citation such as ``TV-VOL-L55P p.4``."""
        return f"{self.doc_id} p.{self.page}" if self.page else self.doc_id

    def label(self) -> str:
        """Citation plus section, version and status, for context blocks and reports."""
        meta = self.metadata
        parts = [self.citation(), str(meta.get("section_title") or "")]
        if meta.get("version"):
            parts.append(f"v{meta['version']}")
        if meta.get("status") and meta.get("status") != "current":
            parts.append(str(meta["status"]).upper())
        if meta.get("note"):
            parts.append(str(meta["note"]))
        return " | ".join(p for p in parts if p)


class MetadataFilter(BaseModel):
    """Exact-match constraints on chunk metadata (all optional, combined with AND).

    Example: ``MetadataFilter(brand="Voltara", model="Lumina 55 Pro")`` keeps only
    chunks of that model's manual, which separates near-duplicate manuals.
    """

    doc_id: str | None = None
    brand: str | None = None
    model: str | None = None
    model_number: str | None = None
    family: str | None = None
    subcategory: str | None = None
    status: str | None = None
    version: str | None = None
    section_title: str | None = None
    content_type: str | None = None

    def constraints(self) -> dict[str, str]:
        """The non-empty constraints as ``{field: value}``."""
        return {k: v for k, v in self.model_dump().items() if v not in (None, "")}

    def is_empty(self) -> bool:
        """True when the filter constrains nothing."""
        return not self.constraints()

    def to_chroma_where(self) -> dict[str, Any] | None:
        """Translate to a Chroma ``where`` clause (``None`` when empty)."""
        items = [{k: {"$eq": v}} for k, v in self.constraints().items()]
        if not items:
            return None
        return items[0] if len(items) == 1 else {"$and": items}

    def matches(self, metadata: dict[str, Any]) -> bool:
        """True when ``metadata`` satisfies every constraint (case-insensitive)."""
        return all(str(metadata.get(k, "")).casefold() == str(v).casefold()
                   for k, v in self.constraints().items())
