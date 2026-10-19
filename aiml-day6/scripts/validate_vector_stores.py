"""Show what is inside the two Chroma vector databases.

For each store this prints:
    1. summary and build configuration (records, documents, embedding model, chunk settings)
    2. distribution and statistics (chunks per document, chunk sizes, content types, metadata coverage)
    3. sample records (ID, text preview, metadata, embedding dimensions)
    4. a cross-check against data/corpus/manifest.json (PASS / FAIL)
    5. sample similarity queries (skip with --skip-queries to avoid embedding API calls)

The script exits with code 1 when a cross-check fails.

Usage:
    uv run scripts/validate_vector_stores.py [--store all|hr|products] [--samples N] [--k 3] [--skip-queries]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_ingestion.config import STORE_CHOICES, IngestionSettings, StoreConfig
from data_ingestion.embeddings import make_embeddings
from data_ingestion.metadata import ManifestIndex
from data_ingestion.validation import (
    FIELD_GROUPS,
    CrossCheck,
    SampleRecord,
    StoreSummary,
    cross_check_manifest,
    run_sample_queries,
    sample_records,
    summarize_store,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", choices=STORE_CHOICES, default="all", help="which vector database to inspect")
    parser.add_argument("--samples", type=int, default=None, help="sample records per store (default: VALIDATION_SAMPLE_SIZE)")
    parser.add_argument("--k", type=int, default=3, help="results per sample query (default: 3)")
    parser.add_argument("--skip-queries", action="store_true", help="do not run sample queries (no API calls)")
    return parser.parse_args(argv)


def heading(text: str) -> None:
    """Print a section heading."""
    print(f"\n  -- {text} " + "-" * max(0, 70 - len(text)))


def print_summary(s: StoreSummary, project_root: Path) -> None:
    """Print counts, build configuration and statistics."""
    cfg = s.store
    heading("Summary")
    print(f"  {'database':<22} {cfg.persist_dir.relative_to(project_root).as_posix()}")
    print(f"  {'collection':<22} {cfg.collection_name}")
    print(f"  {'records':<22} {s.records} chunks from {s.documents} documents ({s.sections} distinct sections)")
    for key in ("embedding_model", "embedding_dimensions", "distance", "chunk_size", "chunk_overlap",
                "strip_headers_footers", "pipeline_version", "ingested_at"):
        print(f"  {key:<22} {s.config.get(key, '-')}")

    heading("Distribution and statistics")
    print(f"  Chunk length (chars)  min/avg/max: {s.char_stats[0]} / {s.char_stats[1]} / {s.char_stats[2]}")
    print(f"  Chunk length (tokens) min/avg/max: {s.token_stats[0]} / {s.token_stats[1]} / {s.token_stats[2]}")
    print(f"  Content types : {dict(s.content_types.most_common())}")
    print(f"  Status        : {dict(s.statuses.most_common())}")
    counts = list(s.chunks_per_document.items())
    print("  Chunks per document:")
    for i in range(0, len(counts), 3):
        print("    " + "   ".join(f"{doc:<18}{n:>4}" for doc, n in counts[i:i + 3]))
    print("  Metadata coverage (% of chunks with the field):")
    for group, fields in FIELD_GROUPS.items():
        values = [s.field_coverage.get(f, 0.0) for f in fields]
        full = all(v == 100.0 for v in values)
        detail = "all 100%" if full else ", ".join(f"{f} {s.field_coverage.get(f, 0.0):g}%" for f in fields)
        print(f"    {group:<18} {detail}")


def print_samples(samples: list[SampleRecord]) -> None:
    """Print sample records with text preview, metadata and embedding head."""
    heading(f"Sample records ({len(samples)})")
    for r in samples:
        preview = " ".join(r.text.split())
        print(f"  [{r.id}]")
        print(f"    text      : {preview[:200]}{'...' if len(preview) > 200 else ''}")
        print(f"    embedding : {r.embedding_dimensions} dimensions, first values {r.embedding_head}")
        print("    metadata  :")
        for key in sorted(r.metadata):
            print(f"      {key:<20} {r.metadata[key]}")


def print_cross_check(check: CrossCheck) -> None:
    """Print the manifest cross-check result."""
    heading("Manifest cross-check")
    print(f"  [{'PASS' if check.passed else 'FAIL'}] expected {check.expected} documents, found {check.found}")
    for label, items in (("missing", check.missing), ("not in manifest for this store", check.unexpected),
                         ("wrong category", check.wrong_category), ("page mismatch", check.page_mismatches)):
        if items:
            print(f"    {label}: {', '.join(items)}")


def print_queries(cfg: StoreConfig, settings: IngestionSettings, k: int) -> None:
    """Run and print the sample similarity queries for one store."""
    heading("Sample queries (cosine relevance, higher is closer)")
    for query, hits in run_sample_queries(cfg, make_embeddings(settings), k).items():
        print(f"  Q: {query}")
        for rank, h in enumerate(hits, start=1):
            print(f"    {rank}. {h.score:.3f}  {h.doc_id} p{h.page_number}  [{h.section_title} | {h.content_type}]")
            print(f"       {h.preview}")


def main(argv: list[str] | None = None) -> int:
    """Validate the selected stores and return a non-zero exit code if a cross-check fails."""
    args = parse_args(argv)
    settings = IngestionSettings.load(PROJECT_ROOT)
    manifest = ManifestIndex.from_corpus(settings.corpus_dir)
    n_samples = args.samples or settings.validation_sample_size
    all_passed = True
    for cfg in settings.selected_stores(args.store):
        print(f"\n=== {cfg.label} ({cfg.key}) " + "=" * 50)
        summary = summarize_store(cfg)
        if not summary.exists:
            print(f"  Store not found at {cfg.persist_dir}. Run scripts/ingest_vector_stores.py first.")
            all_passed = False
            continue
        print_summary(summary, settings.project_root)
        print_samples(sample_records(cfg, n_samples))
        check = cross_check_manifest(cfg, manifest)
        print_cross_check(check)
        all_passed &= check.passed
        if not args.skip_queries:
            if settings.openai_api_key:
                print_queries(cfg, settings, args.k)
            else:
                print("\n  Sample queries skipped: OPENAI_API_KEY is not set.")
    print(f"\nOverall: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
