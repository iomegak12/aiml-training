"""Pre-RAG ingestion: PDFs -> cleaned pages -> chunks with metadata -> OpenAI embeddings -> Chroma.

The package follows the LangChain retrieval building blocks (document loader, text
splitter, embedding model, vector store) and keeps each step in its own module:

- ``config``      -- settings and store definitions loaded from ``.env``
- ``loading``     -- one LangChain ``Document`` per PDF page with common PDF metadata
- ``cleaning``    -- removal of repeated page headers and footers
- ``structure``   -- section titles (from the PDF outline) and content-type hints
- ``chunking``    -- size-based chunking with ``RecursiveCharacterTextSplitter``
- ``metadata``    -- manifest lookup, chunk lineage and Chroma-safe metadata
- ``embeddings``  -- the OpenAI embedding model
- ``vectorstore`` -- opening, resetting and writing the Chroma databases
- ``pipeline``    -- the end-to-end ingestion of one store
- ``validation``  -- read-only summaries, cross-checks and sample queries
"""

__version__ = "0.1.0"
