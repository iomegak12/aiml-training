"""The OpenAI embedding model, wrapped as a LangChain ``OpenAIEmbeddings`` object."""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from data_ingestion.config import IngestionSettings

# Native output sizes of OpenAI embedding models, recorded on each collection for reference.
KNOWN_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def make_embeddings(settings: IngestionSettings) -> OpenAIEmbeddings:
    """Create the embedding model from ``OPENAI_EMBEDDING_MODEL``.

    ``chunk_size`` here is LangChain's name for the number of texts sent per API request,
    so it is set to ``EMBEDDING_BATCH_SIZE``.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in .env; it is required to create embeddings.")
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        chunk_size=settings.embedding_batch_size,
        max_retries=6,
    )


def embedding_dimensions(model: str) -> int | None:
    """Vector size for a known OpenAI embedding model, or ``None`` if unknown."""
    return KNOWN_DIMENSIONS.get(model)
