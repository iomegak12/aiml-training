"""Structure hints for chunks: the section a chunk belongs to and the kind of content it holds.

* ``section_title`` comes from the PDF outline (bookmarks). Each heading is located in the
  page text as a line of its own, and a chunk takes the heading in force at its midpoint.
  Chunks before the first heading are labelled ``Front matter``.
* ``content_type`` is a heuristic: tables extract as many short lines (one per cell),
  lists as lines starting with bullets or numbers, and everything else is prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FRONT_MATTER = "Front matter"
_BULLET = re.compile(r"^(•|-|\*|\d{1,2}[.)])\s+")


@dataclass
class SectionTracker:
    """Tracks the current section while walking through a document page by page.

    Attributes:
        headings: ``(page_number, title)`` pairs from the PDF outline.
        current: Heading in force at the start of the next page.
    """

    headings: list[tuple[int, str]]
    current: str = FRONT_MATTER

    def positions(self, page_number: int, text: str) -> list[tuple[int, str]]:
        """Character offsets in ``text`` where this page's outline headings start (as whole lines)."""
        found = []
        for page, title in self.headings:
            if page != page_number:
                continue
            match = re.search(rf"(?m)^{re.escape(title)}\s*$", text)
            if match:
                found.append((match.start(), title))
        return sorted(found)

    def section_for(self, positions: list[tuple[int, str]], start: int, length: int) -> str:
        """Section title in force at the midpoint of the span ``[start, start + length)`` on the page."""
        midpoint = start + length // 2
        title = self.current
        for offset, heading in positions:
            if offset <= midpoint:
                title = heading
        return title

    def finish_page(self, positions: list[tuple[int, str]]) -> None:
        """Carry the last heading of the page over to the next page."""
        if positions:
            self.current = positions[-1][1]


def classify_content(text: str) -> str:
    """Label a chunk as ``table``, ``list`` or ``prose`` from the shape of its lines."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "prose"
    short = sum(len(ln) < 45 for ln in lines) / len(lines)
    bullets = sum(bool(_BULLET.match(ln)) for ln in lines) / len(lines)
    if len(lines) >= 6 and short >= 0.55:
        return "table"
    if bullets >= 0.3:
        return "list"
    return "prose"
