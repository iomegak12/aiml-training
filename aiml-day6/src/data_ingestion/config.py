"""Settings for the ingestion pipeline, loaded from the project ``.env`` file.

Every value has a sensible default, so a missing key never breaks a run. Two
vector stores are defined: one for HR and compliance documents and one for
product manuals and guides. Each has its own persist directory, collection
name and chunking parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE_CHOICES = ("all", "hr", "products")


def _env_str(name: str, default: str) -> str:
    """Return the stripped value of environment variable ``name`` or ``default`` when unset or empty."""
    value = os.getenv(name, "").strip()
    return value or default


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    """Return environment variable ``name`` as an integer, validating it is at least ``minimum``."""
    raw = os.getenv(name, "").strip()
    value = int(raw) if raw else default
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    """Return environment variable ``name`` as a boolean (true/false, yes/no, 1/0, on/off)."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


@dataclass(frozen=True)
class StoreConfig:
    """Definition of one vector database.

    Attributes:
        key: Short identifier used on the command line (``hr`` or ``products``).
        label: Human-readable name for reports.
        category: Manifest ``category`` whose documents belong in this store.
        source_dir: Folder scanned (recursively) for PDFs to ingest.
        persist_dir: Folder where the persistent Chroma database lives.
        collection_name: Chroma collection inside the database.
        chunk_size: Maximum chunk length in characters.
        chunk_overlap: Characters shared between consecutive chunks of a page.
    """

    key: str
    label: str
    category: str
    source_dir: Path
    persist_dir: Path
    collection_name: str
    chunk_size: int
    chunk_overlap: int

    def __post_init__(self) -> None:
        """Reject chunk settings that the text splitter cannot honour."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(f"{self.key}: chunk_overlap ({self.chunk_overlap}) must be smaller than "
                             f"chunk_size ({self.chunk_size})")


@dataclass(frozen=True)
class IngestionSettings:
    """All settings needed to ingest and validate the vector stores.

    Attributes:
        project_root: Repository root; relative paths in ``.env`` resolve against it.
        corpus_dir: Folder holding the generated PDFs and ``manifest.json``.
        vectorstore_dir: Parent folder of the persistent Chroma databases.
        openai_api_key: Key for the embeddings API (``None`` when not configured).
        embedding_model: OpenAI embedding model name (``OPENAI_EMBEDDING_MODEL``).
        ingest_batch_size: Number of PDFs prepared and embedded in parallel (``INGEST_BATCH_SIZE``).
        embedding_batch_size: Chunks per embeddings request and per Chroma write (``EMBEDDING_BATCH_SIZE``).
        strip_headers_footers: Remove repeated page headers/footers before chunking.
        validation_sample_size: Default number of sample records shown by the validation script.
        stores: Store definitions keyed by ``StoreConfig.key``.
    """

    project_root: Path
    corpus_dir: Path
    vectorstore_dir: Path
    openai_api_key: str | None
    embedding_model: str
    ingest_batch_size: int
    embedding_batch_size: int
    strip_headers_footers: bool
    validation_sample_size: int
    stores: dict[str, StoreConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: Path | None = None) -> IngestionSettings:
        """Load settings from ``<project_root>/.env`` (environment variables take precedence)."""
        root = (project_root or DEFAULT_PROJECT_ROOT).resolve()
        load_dotenv(root / ".env")
        corpus_dir = root / "data" / "corpus"
        vectorstore_dir = (root / _env_str("VECTORSTORE_DIR", "data/vectorstores")).resolve()
        hr_collection = _env_str("HR_COLLECTION_NAME", "hr_policies")
        product_collection = _env_str("PRODUCT_COLLECTION_NAME", "product_manuals")
        stores = {
            "hr": StoreConfig(
                key="hr",
                label="HR policies and compliance",
                category="hr_policy",
                source_dir=corpus_dir / "hr_policies",
                persist_dir=vectorstore_dir / hr_collection,
                collection_name=hr_collection,
                chunk_size=_env_int("HR_CHUNK_SIZE", 800, minimum=100),
                chunk_overlap=_env_int("HR_CHUNK_OVERLAP", 120),
            ),
            "products": StoreConfig(
                key="products",
                label="Product manuals and guides",
                category="product_manual",
                source_dir=corpus_dir / "product_manuals",
                persist_dir=vectorstore_dir / product_collection,
                collection_name=product_collection,
                chunk_size=_env_int("PRODUCT_CHUNK_SIZE", 1200, minimum=100),
                chunk_overlap=_env_int("PRODUCT_CHUNK_OVERLAP", 200),
            ),
        }
        return cls(
            project_root=root,
            corpus_dir=corpus_dir,
            vectorstore_dir=vectorstore_dir,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            embedding_model=_env_str("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            ingest_batch_size=_env_int("INGEST_BATCH_SIZE", 4, minimum=1),
            embedding_batch_size=_env_int("EMBEDDING_BATCH_SIZE", 100, minimum=1),
            strip_headers_footers=_env_bool("STRIP_HEADERS_FOOTERS", True),
            validation_sample_size=_env_int("VALIDATION_SAMPLE_SIZE", 3, minimum=1),
            stores=stores,
        )

    def selected_stores(self, which: str = "all") -> list[StoreConfig]:
        """Return the store definitions selected by ``which`` (``all``, ``hr`` or ``products``)."""
        if which not in STORE_CHOICES:
            raise ValueError(f"store must be one of {STORE_CHOICES}, got {which!r}")
        return list(self.stores.values()) if which == "all" else [self.stores[which]]
