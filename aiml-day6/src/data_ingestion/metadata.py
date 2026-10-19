"""Chunk metadata: corpus manifest fields, chunk lineage and Chroma-safe values.

Metadata groups stored on every chunk:

* **Common PDF metadata** -- added by ``loading`` (source, file, page, PDF info).
* **Corpus manifest fields** -- business metadata from ``data/corpus/manifest.json``
  (document ID, category, brand, model, version, status ...). These power metadata
  filtering, e.g. ``{"status": "current"}`` or ``{"model": "Lumina 55 Pro"}``.
* **Chunk lineage** -- deterministic IDs, positions, sizes and a content hash, used for
  citations, deduplication and idempotent re-ingestion.
* **Structure hints** -- ``section_title`` and ``content_type`` (added by the pipeline).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from data_generation import manifest as corpus_manifest

MANIFEST_FIELDS = (
    "doc_id", "category", "subcategory", "title", "publisher", "brand", "model", "model_number", "family",
    "version", "status", "effective_date", "supersedes", "superseded_by",
)


@dataclass
class ManifestIndex:
    """Look-up of corpus manifest records by PDF file name.

    Attributes:
        records: Manifest document records keyed by file name (e.g. ``HR-POL-001_Leave_Policy_v3.0.pdf``).
    """

    records: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_corpus(cls, corpus_dir: Path) -> ManifestIndex:
        """Load ``manifest.json`` from ``corpus_dir``; an absent manifest yields an empty index."""
        try:
            data = corpus_manifest.load(corpus_dir)
        except FileNotFoundError:
            return cls()
        return cls({Path(doc["file"]).name: doc for doc in data["documents"]})

    def lookup(self, file_name: str) -> dict | None:
        """Return the manifest record for ``file_name``, or ``None`` if the PDF is not in the manifest."""
        return self.records.get(file_name)

    def documents_in_category(self, category: str) -> dict[str, dict]:
        """Manifest records of one category, keyed by ``doc_id``."""
        return {r["doc_id"]: r for r in self.records.values() if r["category"] == category}


def manifest_fields(record: dict | None, file_name: str, default_category: str) -> dict:
    """Business metadata for a document; PDFs outside the manifest get an ID from their file name."""
    if record is None:
        return {"doc_id": Path(file_name).stem, "category": default_category, "status": "unknown"}
    return {key: record.get(key) for key in MANIFEST_FIELDS}


def chunk_id(doc_id: str, page_number: int, index_on_page: int) -> str:
    """Deterministic chunk ID, e.g. ``HR-POL-001-V3.0:p002:c03``. Re-ingestion overwrites, never duplicates."""
    return f"{doc_id}:p{page_number:03d}:c{index_on_page:02d}"


def content_hash(text: str) -> str:
    """Short SHA-256 fingerprint of the chunk text, used to detect unchanged content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def token_encoder(model: str) -> tiktoken.Encoding:
    """Tokenizer matching the embedding model (falls back to ``cl100k_base``)."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def lineage_fields(text: str, index_on_page: int, index_in_doc: int, start_index: int,
                   encoder: tiktoken.Encoding) -> dict:
    """Position and size metadata for one chunk (``chunks_in_doc`` is added once the document is split)."""
    return {
        "chunk_index": index_on_page,
        "chunk_index_in_doc": index_in_doc,
        "start_index": start_index,
        "char_count": len(text),
        "token_count": len(encoder.encode(text)),
        "content_hash": content_hash(text),
    }


def sanitize_for_chroma(metadata: dict) -> dict:
    """Keep only Chroma-friendly values: drop ``None``, join lists with commas, stringify anything else.

    Recent Chroma versions accept lists and ``None``, but flat scalar metadata keeps
    filters simple and stays portable across vector databases.
    """
    clean = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(v) for v in value)
        elif not isinstance(value, (str, int, float, bool)):
            value = str(value)
        clean[key] = value
    return clean
