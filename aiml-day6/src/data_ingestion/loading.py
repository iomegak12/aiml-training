"""PDF loading: one LangChain ``Document`` per page, as in the LangChain semantic-search tutorial.

Each page carries the *common PDF metadata* that any PDF can provide, independent of
this corpus: file identity, page position and the PDF's own information dictionary.
The PDF outline (bookmarks) is read as well, because it tells us where sections start.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader


@dataclass
class LoadedPdf:
    """A PDF split into page Documents plus its outline headings.

    Attributes:
        path: Absolute path of the PDF.
        pages: One ``Document`` per page, in page order.
        headings: ``(page_number, title)`` pairs from the PDF outline, 1-based pages, in reading order.
    """

    path: Path
    pages: list[Document]
    headings: list[tuple[int, str]]


def _info_value(info, key: str) -> str | None:
    """Read ``key`` (e.g. ``/Title``) from a PDF information dictionary, returning ``None`` if absent."""
    if not info:
        return None
    value = info.get(key)
    if value is None:
        return None
    return str(value).strip() or None


def _outline_headings(reader: PdfReader) -> list[tuple[int, str]]:
    """Flatten the PDF outline into ``(page_number, title)`` pairs (1-based), skipping broken entries."""
    headings: list[tuple[int, str]] = []

    def walk(items) -> None:
        """Recursively visit outline entries; nested lists hold sub-headings."""
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            try:
                headings.append((reader.get_destination_page_number(item) + 1, str(item.title).strip()))
            except Exception:  # noqa: BLE001 - malformed bookmarks are simply ignored
                continue

    try:
        walk(reader.outline)
    except Exception:  # noqa: BLE001 - PDFs without a readable outline
        return []
    return headings


def common_pdf_metadata(path: Path, reader: PdfReader, project_root: Path) -> dict:
    """Metadata every PDF can provide: source path, file facts and the PDF information dictionary."""
    info = reader.metadata
    try:
        source = path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        source = path.resolve().as_posix()
    return {
        "source": source,
        "file_name": path.name,
        "file_size_bytes": path.stat().st_size,
        "total_pages": len(reader.pages),
        "pdf_title": _info_value(info, "/Title"),
        "pdf_author": _info_value(info, "/Author"),
        "pdf_subject": _info_value(info, "/Subject"),
        "pdf_keywords": _info_value(info, "/Keywords"),
        "pdf_creator": _info_value(info, "/Creator"),
    }


def load_pdf_pages(path: Path, project_root: Path) -> LoadedPdf:
    """Load ``path`` into page Documents with common PDF metadata and outline headings.

    ``page`` follows the LangChain convention (0-based); ``page_number`` is the 1-based
    number a reader sees, used for citations and the golden Q&A set.
    """
    reader = PdfReader(path)
    common = common_pdf_metadata(path, reader, project_root)
    pages = [
        Document(page_content=page.extract_text() or "", metadata={**common, "page": i, "page_number": i + 1})
        for i, page in enumerate(reader.pages)
    ]
    return LoadedPdf(path=path, pages=pages, headings=_outline_headings(reader))
