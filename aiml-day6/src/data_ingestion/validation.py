"""Read-only inspection of the vector stores for the validation script.

Every function returns plain dataclasses; printing is left to the script so the same
results could feed a notebook, a test or a dashboard.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field

from langchain_core.embeddings import Embeddings

from data_ingestion.config import StoreConfig
from data_ingestion.metadata import ManifestIndex
from data_ingestion.vectorstore import collection_metadata, open_store, record_count

# Metadata fields by group. "optional" fields only apply to some documents (e.g. brand for
# products, superseded_by for old policy versions), so their coverage is below 100% by design.
FIELD_GROUPS = {
    "common_pdf": ("source", "file_name", "file_size_bytes", "page", "page_number", "total_pages", "pdf_title",
                   "pdf_author", "pdf_subject", "pdf_keywords", "pdf_creator"),
    "manifest": ("doc_id", "category", "subcategory", "title", "publisher", "version", "status", "effective_date"),
    "manifest_optional": ("brand", "model", "model_number", "family", "supersedes", "superseded_by"),
    "lineage": ("chunk_id", "chunk_index", "chunk_index_in_doc", "chunks_in_doc", "start_index", "char_count",
                "token_count", "content_hash"),
    "structure": ("section_title", "content_type"),
}
EXPECTED_FIELDS = tuple(f for fields in FIELD_GROUPS.values() for f in fields)

SAMPLE_QUERIES = {
    "hr": [
        "How many days of earned leave does an employee get per year?",
        "What is the daily per diem for travel to a Tier X city?",
        "How soon must a suspected personal data breach be reported?",
    ],
    "products": [
        "What is the refresh rate of the Voltara Lumina 55 Pro?",
        "How do I activate an eSIM on the Nexora Aria 12?",
        "What does error code E-715 mean?",
    ],
}


@dataclass
class StoreSummary:
    """Counts, build configuration and statistics of one store."""

    store: StoreConfig
    exists: bool
    records: int = 0
    documents: int = 0
    config: dict = field(default_factory=dict)
    chunks_per_document: dict[str, int] = field(default_factory=dict)
    char_stats: tuple[int, float, int] = (0, 0.0, 0)
    token_stats: tuple[int, float, int] = (0, 0.0, 0)
    content_types: Counter = field(default_factory=Counter)
    statuses: Counter = field(default_factory=Counter)
    sections: int = 0
    field_coverage: dict[str, float] = field(default_factory=dict)


@dataclass
class SampleRecord:
    """One stored chunk as Chroma holds it."""

    id: str
    text: str
    metadata: dict
    embedding_dimensions: int
    embedding_head: list[float]


@dataclass
class CrossCheck:
    """Comparison of a store's contents with the corpus manifest."""

    passed: bool
    expected: int
    found: int
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    wrong_category: list[str] = field(default_factory=list)
    page_mismatches: list[str] = field(default_factory=list)


@dataclass
class QueryHit:
    """One retrieved chunk for a sample query."""

    doc_id: str
    page_number: int
    section_title: str
    content_type: str
    score: float
    preview: str


def _stats(values: list[int]) -> tuple[int, float, int]:
    """``(min, mean, max)`` of ``values``, or zeros for an empty list."""
    return (min(values), round(statistics.mean(values), 1), max(values)) if values else (0, 0.0, 0)


def store_exists(cfg: StoreConfig) -> bool:
    """True when the store's persist directory contains a Chroma database."""
    return (cfg.persist_dir / "chroma.sqlite3").exists()


def summarize_store(cfg: StoreConfig) -> StoreSummary:
    """Record counts, collection build info, chunk statistics and metadata coverage."""
    if not store_exists(cfg):
        return StoreSummary(store=cfg, exists=False)
    store = open_store(cfg)
    data = store.get(include=["metadatas"])
    metas = [m or {} for m in data["metadatas"]]
    per_doc = Counter(m.get("doc_id", "?") for m in metas)
    coverage = {f: round(100 * sum(f in m for m in metas) / len(metas), 1) if metas else 0.0 for f in EXPECTED_FIELDS}
    return StoreSummary(
        store=cfg,
        exists=True,
        records=record_count(store),
        documents=len(per_doc),
        config=collection_metadata(store),
        chunks_per_document=dict(sorted(per_doc.items())),
        char_stats=_stats([m.get("char_count", 0) for m in metas]),
        token_stats=_stats([m.get("token_count", 0) for m in metas]),
        content_types=Counter(m.get("content_type", "unknown") for m in metas),
        statuses=Counter(m.get("status", "unknown") for m in metas),
        sections=len({(m.get("doc_id"), m.get("section_title")) for m in metas}),
        field_coverage=coverage,
    )


def sample_records(cfg: StoreConfig, n: int) -> list[SampleRecord]:
    """``n`` records spread evenly across the store (deterministic, so runs are comparable)."""
    if not store_exists(cfg):
        return []
    store = open_store(cfg)
    ids = sorted(store.get(include=[])["ids"])
    if not ids:
        return []
    step = max(1, len(ids) // n)
    chosen = ids[::step][:n]
    data = store.get(ids=chosen, include=["documents", "metadatas", "embeddings"])
    records = []
    for rid, text, meta, vector in zip(data["ids"], data["documents"], data["metadatas"], data["embeddings"], strict=True):
        vector = list(vector) if vector is not None else []
        records.append(SampleRecord(rid, text or "", meta or {}, len(vector), [round(float(v), 5) for v in vector[:5]]))
    return sorted(records, key=lambda r: r.id)


def cross_check_manifest(cfg: StoreConfig, manifest: ManifestIndex) -> CrossCheck:
    """Check that the store holds exactly the manifest documents of its category, with every page."""
    expected = manifest.documents_in_category(cfg.category)
    if not store_exists(cfg):
        return CrossCheck(False, len(expected), 0, missing=sorted(expected))
    metas = [m or {} for m in open_store(cfg).get(include=["metadatas"])["metadatas"]]
    pages: dict[str, set[int]] = {}
    categories: dict[str, set[str]] = {}
    for m in metas:
        pages.setdefault(m.get("doc_id", "?"), set()).add(m.get("page_number", 0))
        categories.setdefault(m.get("doc_id", "?"), set()).add(m.get("category", "?"))
    found = set(pages)
    check = CrossCheck(
        passed=True,
        expected=len(expected),
        found=len(found),
        missing=sorted(set(expected) - found),
        unexpected=sorted(found - set(expected)),
        wrong_category=sorted(d for d, cats in categories.items() if cats != {cfg.category}),
        page_mismatches=sorted(
            f"{d}: {len(pages[d])} of {rec['pages']} pages" for d, rec in expected.items()
            if d in pages and len(pages[d]) != rec["pages"]
        ),
    )
    check.passed = not (check.missing or check.unexpected or check.wrong_category or check.page_mismatches)
    return check


def run_sample_queries(cfg: StoreConfig, embeddings: Embeddings, k: int = 3) -> dict[str, list[QueryHit]]:
    """Run the store's sample queries and return the top-``k`` hits for each (one embedding call per query)."""
    store = open_store(cfg, embeddings)
    results = {}
    for query in SAMPLE_QUERIES.get(cfg.key, []):
        hits = []
        for doc, score in store.similarity_search_with_relevance_scores(query, k=k):
            m = doc.metadata
            preview = " ".join(doc.page_content.split())[:110]
            hits.append(QueryHit(m.get("doc_id", "?"), m.get("page_number", 0), m.get("section_title", "-"),
                                 m.get("content_type", "-"), round(score, 3), preview))
        results[query] = hits
    return results
