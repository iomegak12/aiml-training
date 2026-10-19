"""The Coordinator: a LangGraph workflow that plans, dispatches specialists in parallel, reflects and answers."""

from agentic_rag.graph.builder import build_graph, export_mermaid, mermaid
from agentic_rag.graph.service import CoordinatorService, GraphResult

__all__ = ["CoordinatorService", "GraphResult", "build_graph", "export_mermaid", "mermaid"]
