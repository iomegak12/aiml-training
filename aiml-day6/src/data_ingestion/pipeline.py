"""End-to-end ingestion of one vector store.

For every PDF in the store's source folder:

    load pages -> strip headers/footers -> split pages into chunks -> attach metadata
    -> compare with what the store already holds -> embed changed documents -> upsert

Documents are processed in groups of ``INGEST_BATCH_SIZE``: the documents of a group are
prepared and embedded in parallel threads (embedding is the slow, network-bound step),
then written to Chroma one at a time. Re-running is idempotent and cheap:

* unchanged documents (same chunk IDs and content hashes) are skipped without API calls,
* changed documents have their old chunks deleted before the new ones are written,
* documents no longer on disk are removed from the store,
* a different embedding model than the one recorded on the collection forces a rebuild.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from data_ingestion import __version__
from data_ingestion.chunking import build_splitter, split_page
from data_ingestion.cleaning import normalize_pages, strip_headers_footers
from data_ingestion.config import IngestionSettings, StoreConfig
from data_ingestion.embeddings import embedding_dimensions
from data_ingestion.loading import load_pdf_pages
from data_ingestion.metadata import (
    ManifestIndex,
    chunk_id,
    lineage_fields,
    manifest_fields,
    sanitize_for_chroma,
    token_encoder,
)
from data_ingestion.structure import SectionTracker, classify_content
from data_ingestion.vectorstore import (
    collection_metadata,
    delete_document,
    existing_fingerprints,
    open_store,
    record_count,
    reset_store,
    upsert_chunks,
    write_collection_metadata,
)


@dataclass
class PreparedDocument:
    """A PDF turned into chunks that are ready to embed.

    Attributes:
        doc_id: Document identifier (from the manifest, or the file name).
        file: Path of the PDF relative to the project root.
        pages: Number of pages in the PDF.
        chunks: Chunk Documents with complete, Chroma-safe metadata.
        ids: Deterministic chunk IDs, aligned with ``chunks``.
        removed_lines: Header/footer lines stripped before chunking.
        sections: Number of distinct section titles found.
    """

    doc_id: str
    file: str
    pages: int
    chunks: list[Document]
    ids: list[str]
    removed_lines: int
    sections: int

    def fingerprint(self) -> dict[str, str]:
        """``{chunk_id: content_hash}``, compared with the store to detect unchanged documents."""
        return {cid: c.metadata["content_hash"] for cid, c in zip(self.ids, self.chunks, strict=True)}


@dataclass
class DocumentResult:
    """Outcome of ingesting one document (``status`` is ``added``, ``updated`` or ``unchanged``)."""

    doc_id: str
    file: str
    pages: int
    chunks: int
    sections: int
    removed_lines: int
    status: str


@dataclass
class StoreReport:
    """Summary of one store's ingestion run."""

    store: StoreConfig
    documents: list[DocumentResult] = field(default_factory=list)
    removed_documents: list[str] = field(default_factory=list)
    rebuilt: bool = False
    records_in_store: int = 0
    seconds: float = 0.0

    @property
    def embedded_chunks(self) -> int:
        """Chunks sent to the embeddings API in this run."""
        return sum(d.chunks for d in self.documents if d.status != "unchanged")


def discover_pdfs(cfg: StoreConfig) -> list[Path]:
    """All PDFs under the store's source folder, sorted for a stable order."""
    return sorted(cfg.source_dir.rglob("*.pdf"))


def prepare_document(path: Path, cfg: StoreConfig, settings: IngestionSettings, manifest: ManifestIndex) -> PreparedDocument:
    """Load, clean, split and annotate one PDF (no API calls)."""
    loaded = load_pdf_pages(path, settings.project_root)
    pages = normalize_pages(loaded.pages)
    pages, removed = strip_headers_footers(pages) if settings.strip_headers_footers else (pages, 0)
    business = manifest_fields(manifest.lookup(path.name), path.name, cfg.category)
    doc_id = business["doc_id"]
    splitter = build_splitter(cfg.chunk_size, cfg.chunk_overlap)
    encoder = token_encoder(settings.embedding_model)
    tracker = SectionTracker(loaded.headings)

    chunks: list[Document] = []
    ids: list[str] = []
    for page in pages:
        page_number = page.metadata["page_number"]
        positions = tracker.positions(page_number, page.page_content)
        for index_on_page, piece in enumerate(split_page(page, splitter)):
            text = piece.page_content
            start = piece.metadata.get("start_index", 0)
            meta = {
                **piece.metadata,
                **business,
                **lineage_fields(text, index_on_page, len(chunks), start, encoder),
                "section_title": tracker.section_for(positions, start, len(text)),
                "content_type": classify_content(text),
            }
            ids.append(chunk_id(doc_id, page_number, index_on_page))
            chunks.append(Document(page_content=text, metadata=meta))
        tracker.finish_page(positions)

    for chunk, cid in zip(chunks, ids, strict=True):
        chunk.metadata["chunks_in_doc"] = len(chunks)
        chunk.metadata["chunk_id"] = cid
        chunk.metadata = sanitize_for_chroma(chunk.metadata)
    return PreparedDocument(
        doc_id=doc_id,
        file=loaded.pages[0].metadata["source"] if loaded.pages else path.name,
        pages=len(loaded.pages),
        chunks=chunks,
        ids=ids,
        removed_lines=removed,
        sections=len({c.metadata.get("section_title") for c in chunks}),
    )


def _prepare_and_embed(path: Path, cfg: StoreConfig, settings: IngestionSettings, manifest: ManifestIndex,
                       embeddings: Embeddings, known: dict[str, dict[str, str]]):
    """Worker: prepare one PDF and embed its chunks unless the store already holds identical chunks."""
    doc = prepare_document(path, cfg, settings, manifest)
    if known.get(doc.doc_id) == doc.fingerprint():
        return doc, None
    vectors = embeddings.embed_documents([c.page_content for c in doc.chunks]) if doc.chunks else []
    return doc, vectors


def build_collection_metadata(cfg: StoreConfig, settings: IngestionSettings, documents: int) -> dict:
    """Self-describing build information stored on the Chroma collection."""
    return sanitize_for_chroma({
        "store": cfg.key,
        "label": cfg.label,
        "category": cfg.category,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": embedding_dimensions(settings.embedding_model),
        "chunk_size": cfg.chunk_size,
        "chunk_overlap": cfg.chunk_overlap,
        "strip_headers_footers": settings.strip_headers_footers,
        "distance": "cosine",
        "documents": documents,
        "pipeline_version": __version__,
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def ingest_store(cfg: StoreConfig, settings: IngestionSettings, embeddings: Embeddings, manifest: ManifestIndex,
                 reset: bool = False, progress=print) -> StoreReport:
    """Synchronise one Chroma store with the PDFs in its source folder and return a report."""
    started = time.perf_counter()
    report = StoreReport(store=cfg)
    store = open_store(cfg, embeddings)

    previous_model = collection_metadata(store).get("embedding_model")
    if reset or (previous_model and previous_model != settings.embedding_model):
        if not reset:
            progress(f"  Embedding model changed ({previous_model} -> {settings.embedding_model}); rebuilding.")
        reset_store(store)
        report.rebuilt = True

    known = existing_fingerprints(store)
    paths = discover_pdfs(cfg)
    if not paths:
        progress(f"  No PDFs found in {cfg.source_dir}")

    with ThreadPoolExecutor(max_workers=settings.ingest_batch_size) as pool:
        for batch_start in range(0, len(paths), settings.ingest_batch_size):
            batch = paths[batch_start:batch_start + settings.ingest_batch_size]
            futures = [pool.submit(_prepare_and_embed, p, cfg, settings, manifest, embeddings, known) for p in batch]
            for future in futures:
                doc, vectors = future.result()
                if vectors is None:
                    status = "unchanged"
                else:
                    status = "updated" if doc.doc_id in known else "added"
                    delete_document(store, doc.doc_id)
                    upsert_chunks(store, doc.ids, [c.page_content for c in doc.chunks],
                                  [c.metadata for c in doc.chunks], vectors, settings.embedding_batch_size)
                report.documents.append(DocumentResult(doc.doc_id, doc.file, doc.pages, len(doc.chunks),
                                                       doc.sections, doc.removed_lines, status))
            progress(f"  {cfg.key}: {min(batch_start + len(batch), len(paths))}/{len(paths)} documents processed")

    on_disk = {d.doc_id for d in report.documents}
    for stale in sorted(set(known) - on_disk):
        delete_document(store, stale)
        report.removed_documents.append(stale)

    write_collection_metadata(store, build_collection_metadata(cfg, settings, len(report.documents)))
    report.records_in_store = record_count(store)
    report.seconds = time.perf_counter() - started
    return report
