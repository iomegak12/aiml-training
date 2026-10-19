"""Render Documents to text-only PDFs with ReportLab.

Only the PDF core fonts (Helvetica family) are used, and nothing but text,
table rules and coloured boxes is drawn, so the PDFs contain no images or
embedded font files.

Each document has a target page range. ``render`` first lays the document
out at standard density and, if the page count falls outside the range,
re-renders at a tighter (or looser) density until it fits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Spacer,
)
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import Table as RLTable
from reportlab.platypus import TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from data_generation.models import Bullets, Document, Notice, Paragraph, Subheading, Table

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN_X

INK = colors.HexColor("#1F2933")
ACCENT = colors.HexColor("#1D4E89")
MUTED = colors.HexColor("#5F6B7A")
RULE = colors.HexColor("#B8C2CC")
HEADER_BG = colors.HexColor("#E4ECF5")
NOTICE_COLORS = {
    "warning": (colors.HexColor("#FDECEA"), colors.HexColor("#B42318")),
    "caution": (colors.HexColor("#FFF6E5"), colors.HexColor("#B54708")),
    "note": (colors.HexColor("#EEF4FB"), ACCENT),
    "superseded": (colors.HexColor("#FDECEA"), colors.HexColor("#B42318")),
}


@dataclass(frozen=True)
class Density:
    name: str
    body: float  # body font size; everything else scales from it
    leading: float
    gap: float  # paragraph spacing


STANDARD = Density("standard", 10, 14, 6)
DENSITIES_TIGHTER = [STANDARD, Density("compact", 9.5, 13, 5), Density("tight", 9, 12, 4)]
DENSITY_RELAXED = Density("relaxed", 10.5, 15.5, 8)


def _styles(d: Density) -> dict[str, ParagraphStyle]:
    cell = d.body - 1.5
    return {
        "body": ParagraphStyle("Body", fontName="Helvetica", fontSize=d.body, leading=d.leading, textColor=INK,
                               spaceAfter=d.gap),
        "h1": ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=d.body + 4, leading=d.leading + 4,
                             textColor=ACCENT, spaceBefore=2 * d.gap, spaceAfter=d.gap, keepWithNext=1),
        "h2": ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=d.body + 1, leading=d.leading,
                             textColor=INK, spaceBefore=d.gap + 2, spaceAfter=d.gap - 2, keepWithNext=1),
        "cell": ParagraphStyle("Cell", fontName="Helvetica", fontSize=cell, leading=cell + 2.5, textColor=INK),
        "cell_head": ParagraphStyle("CellHead", fontName="Helvetica-Bold", fontSize=cell, leading=cell + 2.5,
                                    textColor=INK),
        "caption": ParagraphStyle("Caption", fontName="Helvetica-Oblique", fontSize=cell, leading=cell + 2.5,
                                  textColor=MUTED, spaceBefore=4, spaceAfter=3),
        "notice": ParagraphStyle("Notice", fontName="Helvetica", fontSize=d.body - 0.5, leading=d.leading - 1,
                                 textColor=INK),
        "doc_title": ParagraphStyle("DocTitle", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=ACCENT,
                                    spaceAfter=4),
        "doc_subtitle": ParagraphStyle("DocSubtitle", fontName="Helvetica", fontSize=11, leading=15, textColor=MUTED,
                                       spaceAfter=10),
        "cover_brand": ParagraphStyle("CoverBrand", fontName="Helvetica-Bold", fontSize=14, leading=18,
                                      textColor=MUTED, alignment=TA_CENTER, spaceAfter=14),
        "cover_title": ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=26, leading=31,
                                      textColor=ACCENT, alignment=TA_CENTER, spaceAfter=8),
        "cover_line": ParagraphStyle("CoverLine", fontName="Helvetica", fontSize=12, leading=16, textColor=INK,
                                     alignment=TA_CENTER, spaceAfter=4),
        "cover_small": ParagraphStyle("CoverSmall", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUTED,
                                      alignment=TA_CENTER, spaceAfter=3),
        "toc_title": ParagraphStyle("TocTitle", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=ACCENT,
                                    spaceAfter=8),
        "toc_entry": ParagraphStyle("TocEntry", fontName="Helvetica", fontSize=10, leading=15, textColor=INK),
    }


def markup(text: str) -> str:
    """Escape XML special characters and convert **bold** to ReportLab markup."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text))


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------

def _canvas_class(doc: Document):
    meta = doc.meta
    superseded = meta.status == "superseded"
    left_header = f"{meta.publisher} | {meta.title}"
    right_header = f"{meta.doc_id} | Version {meta.version}"
    footer_left = ("SUPERSEDED VERSION - FOR REFERENCE ONLY" if superseded
                   else ("Internal - for Aranya employees" if meta.category == "hr_policy" else meta.publisher))

    class NumberedCanvas(canvas.Canvas):
        """Defers page output so every page can show 'Page X of Y'."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states: list[dict] = []
            self._page_bookmarks: list[tuple[str, dict]] = []

        def bookmarkPage(self, key, **kwargs):
            # Pages are only emitted in save(), so a bookmark made now would point at the wrong
            # page object. Remember it and register it when its page is actually written.
            self._page_bookmarks.append((key, kwargs))

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._page_bookmarks = []
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                for key, kwargs in state["_page_bookmarks"]:
                    canvas.Canvas.bookmarkPage(self, key, **kwargs)
                self._draw_chrome(total)
                super().showPage()
            super().save()

        def _draw_chrome(self, total: int) -> None:
            page = self._pageNumber
            self.saveState()
            if not (doc.cover and page == 1):
                self.setFont("Helvetica", 8)
                self.setFillColor(MUTED)
                self.drawString(MARGIN_X, PAGE_H - 12 * mm, left_header)
                self.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 12 * mm, right_header)
                self.setStrokeColor(RULE)
                self.setLineWidth(0.5)
                self.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)
            self.setFont("Helvetica-Bold" if superseded else "Helvetica", 8)
            self.setFillColor(NOTICE_COLORS["superseded"][1] if superseded else MUTED)
            self.drawString(MARGIN_X, 10 * mm, footer_left)
            self.setFont("Helvetica", 8)
            self.setFillColor(MUTED)
            self.drawRightString(PAGE_W - MARGIN_X, 10 * mm, f"Page {page} of {total}")
            self.restoreState()

    return NumberedCanvas


class _DocTemplate(BaseDocTemplate):
    """Registers H1 headings in the table of contents and the PDF outline."""

    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(MARGIN_X, MARGIN_BOTTOM, FRAME_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="page", frames=[frame])])
        self._heading_seq = 0

    def beforeDocument(self):
        # multiBuild renders several passes; keys must repeat exactly for the TOC to converge.
        self._heading_seq = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, RLParagraph) and flowable.style.name == "H1":
            self._heading_seq += 1
            text = flowable.getPlainText()
            key = f"h{self._heading_seq}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0, closed=False)
            self.notify("TOCEntry", (0, text, self.page, key))


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------

class _StoryBuilder:
    def __init__(self, density: Density):
        self.st = _styles(density)
        self.gap = density.gap

    def p(self, text: str, style: str) -> RLParagraph:
        return RLParagraph(markup(text), self.st[style])

    def table(self, block: Table) -> list:
        rows = []
        if block.header:
            rows.append([self.p(h, "cell_head") for h in block.header])
        rows += [[self.p(str(c), "cell") for c in row] for row in block.rows]
        ncols = len(rows[0])
        fractions = block.col_widths or [1 / ncols] * ncols
        table = RLTable(rows, colWidths=[f * FRAME_W for f in fractions], repeatRows=1 if block.header else 0,
                        hAlign="LEFT")
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("BACKGROUND", (0, 0), (-1, 0) if block.header else (0, -1), HEADER_BG),
        ]
        table.setStyle(TableStyle(style))
        out = [self.p(block.caption, "caption")] if block.caption else []
        return out + [table, Spacer(1, self.gap + 2)]

    def notice(self, block: Notice) -> list:
        bg, border = NOTICE_COLORS[block.kind]
        box = RLTable([[self.p(block.text, "notice")]], colWidths=[FRAME_W])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 1, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return [box, Spacer(1, self.gap + 2)]

    def bullets(self, block: Bullets) -> list:
        items = [ListItem(self.p(item, "body"), leftIndent=14) for item in block.items]
        # A plain "-" marker: the core-font bullet glyph extracts as a control character (\x7f) in PDF
        # text extractors, which would leak noise into every downstream RAG pipeline.
        kind = {"bulletType": "1", "bulletFormat": "%s."} if block.ordered else {"bulletType": "bullet", "start": "-"}
        size = self.st["body"].fontSize
        return [ListFlowable(items, leftIndent=14, bulletFontName="Helvetica", bulletFontSize=size, **kind),
                Spacer(1, self.gap - 2)]

    def block(self, block) -> list:
        match block:
            case Paragraph():
                return [self.p(block.text, "body")]
            case Subheading():
                return [self.p(block.text, "h2")]
            case Bullets():
                return self.bullets(block)
            case Table():
                return self.table(block)
            case Notice():
                return self.notice(block)
        raise TypeError(f"Unsupported block: {block!r}")

    def cover(self, doc: Document) -> list:
        c = doc.cover
        toc = TableOfContents(levelStyles=[self.st["toc_entry"]], dotsMinLevel=0)
        return [
            Spacer(1, 6 * mm),
            self.p(c["brand"], "cover_brand"),
            self.p(c["product"], "cover_title"),
            self.p(c["product_line"], "cover_line"),
            self.p(c["model_number"], "cover_line"),
            Spacer(1, 6 * mm),
            self.p(c["doc_kind"], "cover_title"),
            self.p(c["edition"], "cover_small"),
            self.p(c["publisher"], "cover_small"),
            self.p(c["note"], "cover_small"),
            Spacer(1, 8 * mm),
            self.p("Contents", "toc_title"),
            toc,
            PageBreak(),
        ]

    def story(self, doc: Document) -> list:
        story: list = []
        if doc.cover:
            story += self.cover(doc)
        else:
            story += [self.p(doc.meta.title, "doc_title"),
                      self.p(f"{doc.meta.publisher} | {doc.meta.subtitle}", "doc_subtitle")]
        for block in doc.preamble:
            story += self.block(block)
        for section in doc.sections:
            if section.page_break_before:
                story.append(PageBreak())
            story.append(self.p(section.title, "h1"))
            for block in section.blocks:
                story += self.block(block)
        return story


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _render_once(doc: Document, path: Path, density: Density) -> int:
    meta = doc.meta
    template = _DocTemplate(
        str(path),
        pagesize=A4,
        title=meta.title,
        author=meta.publisher,
        subject=f"{meta.category} | {meta.doc_id} | version {meta.version} | {meta.status}",
        keywords=", ".join(meta.keywords),
        creator="aiml-day6 corpus_data_generator (synthetic teaching data)",
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
    )
    story = _StoryBuilder(density).story(doc)
    build = template.multiBuild if doc.cover else template.build
    build(story, canvasmaker=_canvas_class(doc))
    return len(PdfReader(path).pages)


def render(doc: Document, corpus_dir: Path) -> tuple[Path, int, str]:
    """Render ``doc`` to PDF, fitting its page range. Returns (path, pages, density name)."""
    out_dir = corpus_dir / doc.meta.relative_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / doc.meta.filename
    low, high = doc.meta.page_range

    pages = _render_once(doc, path, STANDARD)
    if pages < low:
        relaxed = _render_once(doc, path, DENSITY_RELAXED)
        if relaxed >= low:
            return path, relaxed, DENSITY_RELAXED.name
        return path, _render_once(doc, path, STANDARD), STANDARD.name

    used = STANDARD
    for density in DENSITIES_TIGHTER[1:]:
        if pages <= high:
            break
        pages, used = _render_once(doc, path, density), density
    return path, pages, used.name  # still out of range after "tight" -> reported by verify
