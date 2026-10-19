"""Corpus manifest: one metadata record per generated PDF.

The manifest doubles as the metadata source for filtering demonstrations
(brand, model, family, version, status, effective date ...).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from data_generation import __version__
from data_generation.models import Document
from data_generation.rendering import RenderResult

MANIFEST_NAME = "manifest.json"


def write(docs: list[Document], results: dict[str, RenderResult], corpus_dir: Path, mode: str,
          llm_model: str | None, accepted_per_doc: dict[str, int]) -> Path:
    records = []
    for doc in docs:
        m, r = doc.meta, results[doc.meta.doc_id]
        records.append({
            "doc_id": m.doc_id,
            "title": m.title,
            "subtitle": m.subtitle,
            "category": m.category,
            "subcategory": m.subcategory,
            "publisher": m.publisher,
            "brand": m.brand or None,
            "model": m.model or None,
            "model_number": m.model_number or None,
            "family": m.family or None,
            "version": m.version,
            "status": m.status,
            "effective_date": m.effective_date,
            "supersedes": m.supersedes,
            "superseded_by": m.superseded_by,
            "file": r.path.relative_to(corpus_dir).as_posix(),
            "pages": r.pages,
            "page_range": list(m.page_range),
            "layout_density": r.density,
            "llm_enriched_sections": accepted_per_doc.get(m.doc_id, 0),
            "keywords": m.keywords,
        })
    manifest = {
        "generator": f"aiml-day6 data_generation {__version__}",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "llm_model": llm_model if mode == "hybrid" else None,
        "document_count": len(records),
        "documents": records,
    }
    path = corpus_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load(corpus_dir: Path) -> dict:
    return json.loads((corpus_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
