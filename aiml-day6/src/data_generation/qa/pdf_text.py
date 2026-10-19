"""Page-level PDF text extraction shared by the Q&A mapper and the verifier."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


@lru_cache(maxsize=64)
def page_texts(path: Path, mtime: float) -> tuple[str, ...]:
    """Normalised text per page. ``mtime`` is part of the cache key so re-rendered files are re-read."""
    return tuple(normalize(page.extract_text() or "") for page in PdfReader(path).pages)


def pages_containing(path: Path, evidence: list[str]) -> list[int]:
    """1-based page numbers whose text contains every evidence string."""
    needles = [normalize(e) for e in evidence]
    texts = page_texts(path, path.stat().st_mtime)
    return [i for i, text in enumerate(texts, start=1) if all(n in text for n in needles)]
