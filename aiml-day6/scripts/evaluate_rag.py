"""Sampled batch evaluation of the RAG pipelines and the multi-agent graph on the golden Q&A set.

Usage:
    uv run scripts/evaluate_rag.py                          # EVAL_SAMPLE_SIZE questions, all pipelines + judge
    uv run scripts/evaluate_rag.py --sample 10 --no-judge   # retrieval + golden-answer match only (cheaper)
    uv run scripts/evaluate_rag.py --pipelines hybrid advanced --category hr_policy
    uv run scripts/evaluate_rag.py --sample 5 --graph       # also run the full multi-agent graph

Reports are saved to data/eval/. The graph run needs the CRM MCP server only for CRM questions
(the golden set has none), so it works with the server down.
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

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from agentic_rag.config import AgentSettings  # noqa: E402
from agentic_rag.evaluation.batch import (  # noqa: E402
    evaluate_graph,
    evaluate_pipelines,
    load_golden,
    save_report,
    summarize,
)
from agentic_rag.rag import PIPELINES  # noqa: E402

console = Console()


def show(summary: dict) -> None:
    """Print the per-pipeline summary as a table."""
    table = Table(title="Evaluation summary")
    columns = ["n", "errors", "hit_rate", "mrr", "golden_match", "judge_mean", "judge_pass_rate", "latency_mean_s"]
    table.add_column("pipeline")
    for column in columns:
        table.add_column(column, justify="right")
    for pipeline, values in summary.items():
        table.add_row(pipeline, *("-" if values[c] is None else str(values[c]) for c in columns))
    console.print(table)


async def run_graph(settings: AgentSettings, items: list) -> list[dict]:
    """Evaluate the full Coordinator graph on ``items``."""
    from agentic_rag.graph import CoordinatorService
    async with CoordinatorService.open(settings) as service:
        return await evaluate_graph(service, items, progress=console.print)


def main() -> None:
    """Parse arguments, run the evaluation and save the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", type=int, default=None, help="questions to sample (default EVAL_SAMPLE_SIZE)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--pipelines", nargs="*", default=list(PIPELINES), choices=list(PIPELINES))
    parser.add_argument("--category", choices=["hr_policy", "product_manual"], default=None)
    parser.add_argument("--no-judge", action="store_true", help="skip judge scoring of pipeline answers")
    parser.add_argument("--graph", action="store_true", help="also evaluate the full multi-agent graph")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    settings = AgentSettings.load(ROOT)
    items = load_golden(settings, args.sample or settings.eval_sample_size, args.seed,
                        [args.category] if args.category else None)
    console.print(f"[bold]{len(items)} golden questions[/] | pipelines: {', '.join(args.pipelines) or 'none'} | "
                  f"judge: {'off' if args.no_judge else settings.judge_model} | graph: {args.graph}")
    rows = evaluate_pipelines(settings, items, args.pipelines, use_judge=not args.no_judge, workers=args.workers,
                              progress=console.print) if args.pipelines else []
    if args.graph:
        rows += asyncio.run(run_graph(settings, items))
    summary = summarize(rows)
    show(summary)
    path = save_report(settings, "rag-eval", items, rows, summary)
    console.print(f"Report: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
