"""Export the compiled Coordinator graph as Mermaid (docs/diagrams/coordinator_graph.mmd).

The diagram is generated from the real ``StateGraph`` (``get_graph().draw_mermaid()``), so it
always matches the code. Needs OPENAI_API_KEY only to construct the models; no model is called,
and the CRM MCP server may be down (the graph shape does not depend on it).

Usage:
    uv run scripts/export_graph_diagram.py [--out docs/diagrams/coordinator_graph.mmd]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore", message=".*langchain.mcp.*")

from agentic_rag.agents.registry import build_team  # noqa: E402
from agentic_rag.config import AgentSettings  # noqa: E402
from agentic_rag.graph.builder import build_graph, export_mermaid  # noqa: E402
from agentic_rag.mcp_client import load_crm_tools  # noqa: E402


async def main(out: Path) -> None:
    """Build the graph (without memory) and write its Mermaid source."""
    settings = AgentSettings.load(ROOT)
    crm = await load_crm_tools(settings, timeout=3)
    graph = build_graph(settings, build_team(settings, crm), crm)
    path = export_mermaid(graph, out)
    print(f"Wrote {path.relative_to(ROOT)} ({len(path.read_text(encoding='utf-8').splitlines())} lines)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "diagrams" / "coordinator_graph.mmd")
    asyncio.run(main(parser.parse_args().out.resolve()))
