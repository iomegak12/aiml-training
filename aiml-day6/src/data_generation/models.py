"""In-memory document model shared by builders, the LLM enricher and the renderer.

Text in every block is plain text. The only inline markup supported is
``**bold**``; the renderer escapes everything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Paragraph:
    text: str
    enrich: bool = False  # True -> prose the LLM may expand in hybrid mode


@dataclass
class Subheading:
    text: str


@dataclass
class Bullets:
    items: list[str]
    ordered: bool = False


@dataclass
class Table:
    rows: list[list[str]]
    header: list[str] | None = None
    col_widths: list[float] | None = None  # fractions of the frame width
    caption: str | None = None


@dataclass
class Notice:
    text: str
    kind: Literal["warning", "caution", "note", "superseded"] = "note"


Block = Paragraph | Subheading | Bullets | Table | Notice


@dataclass
class Section:
    id: str
    title: str
    blocks: list[Block] = field(default_factory=list)
    facts: dict = field(default_factory=dict)  # grounding facts for the LLM
    page_break_before: bool = False


@dataclass
class DocMeta:
    doc_id: str
    title: str
    subtitle: str
    category: Literal["product_manual", "hr_policy"]
    subcategory: str  # tv | mobile | hr
    publisher: str
    version: str
    effective_date: str
    filename: str
    relative_dir: str
    page_range: tuple[int, int]
    status: Literal["current", "superseded"] = "current"
    brand: str = ""
    model: str = ""
    model_number: str = ""
    family: str = ""
    supersedes: str | None = None
    superseded_by: str | None = None
    keywords: list[str] = field(default_factory=list)
    sibling_models: list[str] = field(default_factory=list)


@dataclass
class Document:
    meta: DocMeta
    sections: list[Section]
    facts: dict
    cover: dict[str, str] = field(default_factory=dict)  # cover page fields (manuals only)
    preamble: list[Block] = field(default_factory=list)  # blocks before section 1
