"""Keyword retrieval with BM25 over every chunk of a store.

Embeddings blur exact tokens such as error codes (``E-715``), model numbers
(``VT-55L7Q``) and policy IDs (``HR-POL-004``). BM25 scores literal term overlap, so it
finds them reliably. The tokenizer keeps hyphenated codes as single tokens *and* adds
their parts, so ``E-715``, ``e715`` and ``715`` all match.
"""

from __future__ import annotations

import re
import threading

from rank_bm25 import BM25Okapi

from agentic_rag.config import AgentSettings
from agentic_rag.retrieval.models import MetadataFilter, RetrievedChunk
from agentic_rag.retrieval.stores import StoreKey, load_all_chunks

_TOKEN = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it its my of on or "
    "the this to was what when where which who why will with you your".split())


def tokenize(text: str) -> list[str]:
    """Lower-case tokens; hyphenated codes yield the whole code, a joined form and each part."""
    tokens: list[str] = []
    for token in _TOKEN.findall(text.lower()):
        if token in STOPWORDS:
            continue
        tokens.append(token)
        parts = re.split(r"[-./]", token)
        if len(parts) > 1:
            tokens.append("".join(parts))
            tokens.extend(p for p in parts if p and p not in STOPWORDS)
    return tokens


class BM25Index:
    """BM25 (Okapi) index over a list of chunks."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        """Tokenize ``chunks`` (title and section are prepended to the text) and build the index."""
        self.chunks = chunks
        corpus = [tokenize(f"{c.title} {c.metadata.get('section_title', '')} {c.text}") for c in chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int, flt: MetadataFilter | None = None) -> list[RetrievedChunk]:
        """Top-``k`` chunks by BM25 score (zero-score chunks are dropped), optionally filtered."""
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        hits: list[RetrievedChunk] = []
        for i in order:
            if scores[i] <= 0 or len(hits) >= k:
                break
            chunk = self.chunks[i]
            if flt and not flt.matches(chunk.metadata):
                continue
            hits.append(chunk.model_copy(update={"score": round(float(scores[i]), 4), "retriever": "bm25",
                                                 "ranks": {"bm25": len(hits) + 1}}))
        return hits


_lock = threading.Lock()
_indexes: dict[str, BM25Index] = {}


def get_bm25_index(settings: AgentSettings, key: StoreKey) -> BM25Index:
    """Build (once per process) and return the BM25 index for store ``key``."""
    cache_key = str(settings.store(key).persist_dir)
    with _lock:
        if cache_key not in _indexes:
            _indexes[cache_key] = BM25Index(load_all_chunks(settings, key))
        return _indexes[cache_key]


def keyword_search(settings: AgentSettings, key: StoreKey, query: str, k: int,
                   flt: MetadataFilter | None = None) -> list[RetrievedChunk]:
    """Top-``k`` chunks of store ``key`` by BM25."""
    return get_bm25_index(settings, key).search(query, k, flt)
