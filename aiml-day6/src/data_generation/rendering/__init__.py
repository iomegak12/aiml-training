"""PDF rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from data_generation.models import Document
from data_generation.rendering.pdf_renderer import render


@dataclass(frozen=True)
class RenderResult:
    path: Path
    pages: int
    density: str


def render_all(docs: list[Document], corpus_dir: Path) -> dict[str, RenderResult]:
    """Render every document; returns doc_id -> RenderResult."""
    results = {}
    for doc in docs:
        path, pages, density = render(doc, corpus_dir)
        results[doc.meta.doc_id] = RenderResult(path, pages, density)
    return results


__all__ = ["RenderResult", "render", "render_all"]
