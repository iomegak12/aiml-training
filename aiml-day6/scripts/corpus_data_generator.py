"""Generate the synthetic RAG teaching corpus (product manuals + HR policies).

This script only coordinates the pipeline; every step lives in the
``data_generation`` package under ``src/``:

    build (templates) -> enrich (optional LLM) -> render PDFs -> manifest -> golden Q&A -> verify

Usage:
    uv run scripts/corpus_data_generator.py generate [--mode template|hybrid] [--only all|products|hr]
                                                     [--refresh] [--effort low|medium|high] [--workers N]
    uv run scripts/corpus_data_generator.py verify
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from data_generation import builders, manifest, qa, rendering, verify
from data_generation.config import REASONING_EFFORTS, Settings
from data_generation.llm import LLMCache, LLMClient, enrich

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="build the corpus, golden Q&A and manifest, then verify")
    gen.add_argument("--mode", choices=["template", "hybrid"], default=None,
                     help="template = offline only; hybrid = LLM-expanded prose (default: hybrid if OPENAI_API_KEY is set)")
    gen.add_argument("--only", choices=builders.ONLY_CHOICES, default="all", help="generate a subset of the corpus")
    gen.add_argument("--refresh", action="store_true", help="ignore the LLM cache and regenerate prose")
    gen.add_argument("--effort", choices=REASONING_EFFORTS, default=None,
                     help="reasoning effort for new LLM requests (default: OPENAI_REASONING_EFFORT from .env); lower is "
                          "faster and cheaper. Cached sections are reused whatever the effort; add --refresh to redo them")
    gen.add_argument("--workers", type=int, default=6,
                     help="concurrent LLM requests (default: 6); raise it for speed, lower it on rate-limit errors")

    sub.add_parser("verify", help="check an existing corpus on disk")
    return parser.parse_args(argv)


def print_checks(checks: list[verify.Check]) -> bool:
    print("\nVerification")
    for check in checks:
        print(f"  [{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    return all(c.passed for c in checks)


def cmd_generate(args: argparse.Namespace, settings: Settings) -> int:
    mode = args.mode or ("hybrid" if settings.llm_available else "template")
    if mode == "hybrid" and not settings.llm_available:
        print("ERROR: hybrid mode needs OPENAI_API_KEY in .env (or use --mode template).", file=sys.stderr)
        return 2
    effort = args.effort or settings.reasoning_effort
    started = time.perf_counter()
    print(f"Mode: {mode}" + (f" | model {settings.openai_model} | reasoning effort {effort}" if mode == "hybrid" else ""))

    # 1. Build documents from catalog facts with template prose.
    docs = builders.build_all(args.only)
    print(f"Built {len(docs)} documents from the catalog")

    # 2. Optionally enrich prose with the LLM (cached, guarded).
    stats = None
    if mode == "hybrid":
        client = LLMClient(settings.openai_api_key, settings.openai_model, effort)
        stats = enrich(docs, client, LLMCache(settings.cache_dir), refresh=args.refresh, workers=args.workers)
        print(f"LLM enrichment: {stats.accepted} accepted, {stats.rejected} rejected (template kept), "
              f"{stats.errors} errors | {stats.api_calls} API calls, {stats.cache_hits} cache hits")

    # 3. Render PDFs into a clean output folder.
    shutil.rmtree(settings.corpus_dir, ignore_errors=True)
    shutil.rmtree(settings.qa_dir, ignore_errors=True)
    results = rendering.render_all(docs, settings.corpus_dir)

    # 4. Manifest and generation report.
    accepted = dict(stats.per_doc_accepted) if stats else {}
    manifest.write(docs, results, settings.corpus_dir, mode, settings.openai_model, accepted)
    report = {"mode": mode, "only": args.only, "reasoning_effort": effort if mode == "hybrid" else None,
              "enrichment": stats.as_dict() if stats else None}
    (settings.corpus_dir / "generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # 5. Golden Q&A with evidence pages from the rendered PDFs.
    items = qa.generate({doc_id: r.path for doc_id, r in results.items()}, settings.corpus_dir, settings.qa_dir)

    print(f"\n{'Document':<20} {'Pages':>5}  {'Layout':<9} {'LLM':>3}  File")
    for doc in docs:
        r = results[doc.meta.doc_id]
        print(f"{doc.meta.doc_id:<20} {r.pages:>5}  {r.density:<9} {accepted.get(doc.meta.doc_id, 0):>3}  "
              f"{r.path.relative_to(settings.project_root).as_posix()}")
    print(f"\nGolden Q&A: {len(items)} questions -> {settings.qa_dir.relative_to(settings.project_root).as_posix()}")
    print(f"Finished in {time.perf_counter() - started:.1f}s")

    # 6. Verify what was written.
    return 0 if print_checks(verify.run(settings.corpus_dir, settings.qa_dir)) else 1


def cmd_verify(settings: Settings) -> int:
    return 0 if print_checks(verify.run(settings.corpus_dir, settings.qa_dir)) else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.load(PROJECT_ROOT)
    if args.command == "generate":
        return cmd_generate(args, settings)
    return cmd_verify(settings)


if __name__ == "__main__":
    sys.exit(main())
