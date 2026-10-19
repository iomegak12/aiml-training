"""Ingest the corpus PDFs into two persistent Chroma vector databases (pre-RAG step).

This script only coordinates the pipeline; every step lives in the ``data_ingestion``
package under ``src/``:

    load PDF pages -> clean -> chunk (size-based) -> metadata -> OpenAI embeddings -> Chroma

Stores (configured in .env):
    hr        HR policies and compliance documents  -> data/vectorstores/<HR_COLLECTION_NAME>
    products  Product manuals and guides            -> data/vectorstores/<PRODUCT_COLLECTION_NAME>

Usage:
    uv run scripts/ingest_vector_stores.py [--store all|hr|products] [--reset]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from data_ingestion.config import STORE_CHOICES, IngestionSettings
from data_ingestion.embeddings import make_embeddings
from data_ingestion.metadata import ManifestIndex
from data_ingestion.pipeline import StoreReport, ingest_store

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", choices=STORE_CHOICES, default="all", help="which vector database to ingest")
    parser.add_argument("--reset", action="store_true",
                        help="empty the selected store(s) first, e.g. after changing chunk size or metadata logic")
    return parser.parse_args(argv)


def print_report(report: StoreReport, project_root: Path) -> None:
    """Print a per-document table and the totals of one store."""
    cfg = report.store
    print(f"\n{cfg.label} -> {cfg.persist_dir.relative_to(project_root).as_posix()} "
          f"(collection '{cfg.collection_name}', chunk {cfg.chunk_size}/{cfg.chunk_overlap})")
    print(f"  {'Document':<18} {'Pages':>5} {'Chunks':>6} {'Sections':>8} {'Hdr/ftr':>7}  Status")
    for d in report.documents:
        print(f"  {d.doc_id:<18} {d.pages:>5} {d.chunks:>6} {d.sections:>8} {d.removed_lines:>7}  {d.status}")
    statuses = {s: sum(d.status == s for d in report.documents) for s in ("added", "updated", "unchanged")}
    print(f"  Documents: {len(report.documents)} ({', '.join(f'{n} {s}' for s, n in statuses.items())})"
          + (f" | removed: {', '.join(report.removed_documents)}" if report.removed_documents else "")
          + (" | store was reset" if report.rebuilt else ""))
    print(f"  Chunks embedded this run: {report.embedded_chunks} | records in store: {report.records_in_store} "
          f"| {report.seconds:.1f}s")


def main(argv: list[str] | None = None) -> int:
    """Ingest the selected stores and print a report for each."""
    args = parse_args(argv)
    settings = IngestionSettings.load(PROJECT_ROOT)
    manifest = ManifestIndex.from_corpus(settings.corpus_dir)
    if not manifest.records:
        print("WARNING: data/corpus/manifest.json not found; documents get IDs from file names only.")
    try:
        embeddings = make_embeddings(settings)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Embedding model: {settings.embedding_model} | parallel documents (INGEST_BATCH_SIZE): "
          f"{settings.ingest_batch_size} | chunks per request (EMBEDDING_BATCH_SIZE): {settings.embedding_batch_size} "
          f"| strip headers/footers: {settings.strip_headers_footers}")
    started = time.perf_counter()
    for cfg in settings.selected_stores(args.store):
        report = ingest_store(cfg, settings, embeddings, manifest, reset=args.reset)
        print_report(report, settings.project_root)
    print(f"\nFinished in {time.perf_counter() - started:.1f}s. "
          "Run scripts/validate_vector_stores.py to inspect the stores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
