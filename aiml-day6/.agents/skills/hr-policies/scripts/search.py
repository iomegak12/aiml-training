"""Search the HR policy vector store from the shell (for Claude Code, Codex and Copilot).

Usage (from anywhere inside the aiml-day6 repository):
    uv run python <skill folder>/scripts/search.py "How many casual leaves do I get?"
    uv run python <skill folder>/scripts/search.py "per diem Tier X" --pipeline hybrid --no-answer

Pipelines: hybrid | advanced (default) | multi_query | corrective. Prints JSON with the answer, the sources
(document ID, page, quote) and the pipeline trace. Requires the vector stores (`make ingest`) and OPENAI_API_KEY.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

STORE = "hr"


def project_root() -> Path:
    """Walk up from this file (or the working directory) to the repository that contains src/agentic_rag."""
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for folder in (start, *start.parents):
            if (folder / "src" / "agentic_rag").is_dir() and (folder / "pyproject.toml").is_file():
                return folder
    sys.exit("Could not find the aiml-day6 repository (src/agentic_rag). Run from inside the repo.")


def main() -> None:
    """Parse arguments, run the chosen RAG pipeline and print its compact JSON result."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question")
    parser.add_argument("--pipeline", default="advanced", choices=["hybrid", "advanced", "multi_query", "corrective"])
    parser.add_argument("--k", type=int, default=None, help="passages in the context")
    parser.add_argument("--model", default=None, help="product model filter, e.g. 'Lumina 55 Pro'")
    parser.add_argument("--brand", default=None, help="brand filter, e.g. Voltara")
    parser.add_argument("--no-answer", action="store_true", help="retrieval only, no answer generation")
    args = parser.parse_args()

    root = project_root()
    sys.path.insert(0, str(root / "src"))
    from agentic_rag.config import AgentSettings
    from agentic_rag.rag import PIPELINES
    from agentic_rag.retrieval import MetadataFilter

    flt = MetadataFilter(model=args.model, brand=args.brand)
    result = PIPELINES[args.pipeline](AgentSettings.load(root), STORE, args.question, k=args.k,
                                      flt=None if flt.is_empty() else flt, generate=not args.no_answer)
    print(result.to_tool_output())


if __name__ == "__main__":
    main()
