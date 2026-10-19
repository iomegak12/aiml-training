"""Context preparation: de-duplicate, order and fit retrieved chunks into a token budget.

"Best order" here means: documents ordered by their best-ranked chunk, and chunks of the
same document kept in reading order (page, then position). Related passages then sit
next to each other, which helps the model read tables and multi-chunk sections.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentic_rag.retrieval.models import RetrievedChunk
from data_ingestion.metadata import token_encoder

DEFAULT_CONTEXT_TOKENS = 3500


@dataclass
class ContextPack:
    """A prompt-ready context block and the sources it contains.

    Attributes:
        text: Context with ``[S1]``, ``[S2]`` ... source headers.
        sources: ``(source_id, chunk)`` pairs in the order they appear.
        tokens: Token count of ``text``.
        dropped: Chunks left out because the budget was reached.
    """

    text: str
    sources: list[tuple[str, RetrievedChunk]] = field(default_factory=list)
    tokens: int = 0
    dropped: int = 0

    def citation_for(self, source_id: str) -> str | None:
        """Citation string (``DOC p.N``) for a source ID such as ``S2``."""
        return next((c.citation() for sid, c in self.sources if sid == source_id), None)


def dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Drop repeated chunk IDs, keeping the first (best-ranked) occurrence."""
    seen: set[str] = set()
    return [c for c in chunks if not (c.chunk_id in seen or seen.add(c.chunk_id))]


def order_for_reading(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Group chunks by document (best document first) and sort each group in reading order."""
    doc_rank: dict[str, int] = {}
    for i, chunk in enumerate(chunks):
        doc_rank.setdefault(chunk.doc_id, i)
    return sorted(chunks, key=lambda c: (doc_rank[c.doc_id], c.page or 0, c.metadata.get("chunk_index_in_doc", 0)))


def build_context(chunks: list[RetrievedChunk], max_tokens: int = DEFAULT_CONTEXT_TOKENS,
                  encoding_model: str = "gpt-4o") -> ContextPack:
    """Build a ``ContextPack`` from ranked ``chunks`` within ``max_tokens``.

    The budget is applied in *relevance* order (so the least relevant chunks are the ones
    dropped), then the kept chunks are re-ordered for reading.
    """
    encoder = token_encoder(encoding_model)
    kept: list[RetrievedChunk] = []
    used = 0
    unique = dedupe(chunks)
    for chunk in unique:
        cost = len(encoder.encode(chunk.text)) + 20
        if kept and used + cost > max_tokens:
            continue
        kept.append(chunk)
        used += cost
    ordered = order_for_reading(kept)
    sources = [(f"S{i}", c) for i, c in enumerate(ordered, start=1)]
    text = "\n\n".join(f"[{sid}] {c.label()}\n{c.text.strip()}" for sid, c in sources)
    return ContextPack(text=text, sources=sources, tokens=len(encoder.encode(text)), dropped=len(unique) - len(kept))
