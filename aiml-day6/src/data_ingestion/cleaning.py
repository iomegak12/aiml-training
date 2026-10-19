"""Text clean-up before chunking: extraction artefacts and repeated page headers/footers.

``normalize_extracted_text`` always runs; it repairs list bullets that extractors put on a
line of their own and removes stray control characters.

Running headers ("Publisher | Title", "DOC-ID | Version 1.2") and footers ("Page 3 of 10")
appear on almost every page. Left in place they end up in every chunk, dilute the
embeddings and make unrelated chunks look similar. The detection here is generic and
works on any PDF:

1. Only lines at the *edges* of a page (the first and last few lines) are candidates,
   so repeated table cells or phrases in the body are never touched.
2. A candidate is removed when the same line appears on at least ``min_share`` of the
   document's pages, or when it looks like a page number ("Page 3 of 10", "3 / 10").
"""

from __future__ import annotations

import math
import re
from collections import Counter

from langchain_core.documents import Document

PAGE_NUMBER = re.compile(r"^\s*(page\s+\d+(\s+of\s+\d+)?|\d+\s*/\s*\d+|-\s*\d+\s*-)\s*$", re.IGNORECASE)
EDGE_LINES = 4
# Glyphs that PDF extractors often emit on a line of their own in front of a list item.
BULLET_GLYPHS = {"-", "*", "•", "●", "■", "▪", "◦", "–", "\x7f", "�", "o"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NUMBER_MARKER = re.compile(r"^\d{1,2}[.)]$")  # "1." or "2)" extracted on its own line


def normalize_extracted_text(text: str) -> str:
    """Repair common PDF text-extraction artefacts.

    * A bullet glyph or list number extracted on its own line is joined to the item that follows
      ("-\\nItem" -> "- Item", "1.\\nStep" -> "1. Step").
    * Remaining control characters (e.g. ``\\x7f`` for an unmapped bullet glyph) are removed.
    """
    lines = text.splitlines()
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if i + 1 < len(lines) and (line in BULLET_GLYPHS or _NUMBER_MARKER.match(line)):
            marker = "-" if line in BULLET_GLYPHS else line
            merged.append(f"{marker} {lines[i + 1].strip()}")
            i += 2
            continue
        merged.append(lines[i])
        i += 1
    return _CONTROL.sub("", "\n".join(merged))


def normalize_pages(pages: list[Document]) -> list[Document]:
    """Apply ``normalize_extracted_text`` to every page, returning new Documents."""
    return [Document(page_content=normalize_extracted_text(p.page_content), metadata=dict(p.metadata)) for p in pages]


def _lines(text: str) -> list[str]:
    """Split page text into stripped, non-empty lines."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _edge_lines(lines: list[str], edge: int = EDGE_LINES) -> list[str]:
    """Return the first and last ``edge`` lines of a page (without duplicates for short pages)."""
    if len(lines) <= 2 * edge:
        return lines
    return lines[:edge] + lines[-edge:]


def find_repeating_lines(pages: list[str], min_share: float = 0.6) -> set[str]:
    """Edge lines that repeat on at least ``min_share`` of the pages (and on at least 2 pages)."""
    if len(pages) < 2:
        return set()
    counts = Counter(line for text in pages for line in set(_edge_lines(_lines(text))))
    threshold = max(2, math.ceil(min_share * len(pages)))
    return {line for line, n in counts.items() if n >= threshold}


def strip_headers_footers(pages: list[Document], min_share: float = 0.6) -> tuple[list[Document], int]:
    """Return copies of ``pages`` without repeated headers/footers, and the number of lines removed."""
    repeating = find_repeating_lines([p.page_content for p in pages], min_share)
    cleaned, removed = [], 0
    for page in pages:
        lines = _lines(page.page_content)
        edges = set(_edge_lines(lines))
        kept = [ln for ln in lines if not (ln in edges and (ln in repeating or PAGE_NUMBER.match(ln)))]
        removed += len(lines) - len(kept)
        cleaned.append(Document(page_content="\n".join(kept), metadata=dict(page.metadata)))
    return cleaned, removed
