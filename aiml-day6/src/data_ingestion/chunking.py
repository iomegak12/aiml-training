"""Size-based chunking with LangChain's ``RecursiveCharacterTextSplitter``.

The splitter tries paragraph breaks first, then line breaks, then spaces, so chunks stay
under ``chunk_size`` characters while breaking at the most natural boundary available.
Pages are split one at a time (page-level split), so a chunk never crosses a page and
always has an exact page number for citations.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def build_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    """Create the text splitter. ``add_start_index`` records each chunk's offset within its page."""
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True)


def split_page(page: Document, splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    """Split one page into chunks; each chunk inherits the page metadata plus ``start_index``."""
    if not page.page_content.strip():
        return []
    return splitter.split_documents([page])
