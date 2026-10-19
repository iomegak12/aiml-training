"""RAG pipelines (hybrid, advanced, multi-query, corrective) and the steps they share."""

from agentic_rag.rag.advanced import advanced_rag, advanced_retrieve
from agentic_rag.rag.answer import I_DONT_KNOW, GroundedAnswer, compose_result, generate_answer
from agentic_rag.rag.context import ContextPack, build_context
from agentic_rag.rag.corrective import corrective_rag
from agentic_rag.rag.hybrid_rag import hybrid_rag
from agentic_rag.rag.multi_query import multi_query_rag
from agentic_rag.rag.result import RagResult, SourceRef

PIPELINES = {
    "hybrid": hybrid_rag,
    "advanced": advanced_rag,
    "multi_query": multi_query_rag,
    "corrective": corrective_rag,
}

__all__ = [
    "I_DONT_KNOW", "PIPELINES", "ContextPack", "GroundedAnswer", "RagResult", "SourceRef", "advanced_rag",
    "advanced_retrieve", "build_context", "compose_result", "corrective_rag", "generate_answer", "hybrid_rag",
    "multi_query_rag",
]
