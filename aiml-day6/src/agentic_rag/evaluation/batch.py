"""Sampled batch evaluation on the golden Q&A set.

Two levels are measured on a stratified sample of ``data/golden_qa/golden_qa.jsonl``:

1. **RAG pipelines** (hybrid, advanced, multi-query, corrective):
   - ``hit@k``: an expected source document is among the ranked chunks,
   - ``mrr``: reciprocal rank of the first chunk from an expected document,
   - ``golden_match``: the short golden answer (e.g. "60 Hz") appears in the generated answer,
   - judge ``overall`` score and pass rate (optional; costs one judge call per answer),
   - latency.
2. **Full multi-agent graph**: judge score/pass rate, attempts, specialist runs, golden match, latency.

Results are written to ``data/eval/<name>-<timestamp>.json``.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_rag.config import AgentSettings
from agentic_rag.evaluation.judge import judge_answer
from agentic_rag.rag import PIPELINES
from agentic_rag.retrieval.stores import StoreKey

CATEGORY_STORE: dict[str, StoreKey] = {"hr_policy": "hr", "product_manual": "products"}


@dataclass
class GoldenItem:
    """One golden question with its expected answer and source documents."""

    id: str
    question: str
    answer: str
    category: str
    question_type: str
    difficulty: str
    doc_ids: list[str]

    @property
    def store(self) -> StoreKey:
        """Vector store that holds the answer."""
        return CATEGORY_STORE.get(self.category, "products")


def load_golden(settings: AgentSettings, sample: int | None = None, seed: int = 7,
                categories: Sequence[str] | None = None) -> list[GoldenItem]:
    """Load the golden set; with ``sample`` draw a stratified sample (by category and question type)."""
    items = []
    for line in settings.golden_qa_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if categories and row["category"] not in categories:
            continue
        items.append(GoldenItem(id=row["id"], question=row["question"], answer=str(row["answer"]),
                                category=row["category"], question_type=row.get("question_type", ""),
                                difficulty=row.get("difficulty", ""),
                                doc_ids=[s["doc_id"] for s in row.get("sources", [])]))
    if not sample or sample >= len(items):
        return items
    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[GoldenItem]] = defaultdict(list)
    for item in items:
        groups[(item.category, item.question_type)].append(item)
    for group in groups.values():
        rng.shuffle(group)
    picked: list[GoldenItem] = []
    while len(picked) < sample:  # round-robin over strata keeps the sample balanced
        for key in sorted(groups):
            if groups[key] and len(picked) < sample:
                picked.append(groups[key].pop())
    return picked


_STOP = frozenset("a an and the of for in on at to is are be by with per or than not no it its this that "
                  "which from as all".split())
_IDK = re.compile(r"(don't|do not|cannot|can't) (know|find|confirm)|not (available|covered|mentioned|found)", re.I)


def _tokens(text: str) -> list[str]:
    """Lower-case tokens; thousands separators removed so "5,00,000" and "500000" match."""
    return re.findall(r"[a-z]+-?\d+|\d+(?:\.\d+)?|[a-z]+", re.sub(r"(?<=\d),(?=\d)", "", text.lower()))


def golden_match(golden: str, answer: str, min_word_recall: float = 0.6) -> bool:
    """Key-fact match between the golden answer and a generated ``answer``.

    - Unanswerable golden items ("Not available in the corpus") match an "I don't know" style answer.
    - Every number and code in the golden answer (``105``, ``LX-93``, ``500000``) must appear in the answer.
    - At least ``min_word_recall`` of the golden content words must appear.
    """
    if not golden or not answer:
        return False
    if golden.lower().startswith("not available"):
        return bool(_IDK.search(answer))
    gold = [t for t in _tokens(golden) if t not in _STOP]
    have = set(_tokens(answer))
    facts = [t for t in gold if any(ch.isdigit() for ch in t)]
    words = [t for t in gold if t not in facts]
    if any(f not in have for f in facts):
        return False
    return not words or sum(w in have for w in words) / len(words) >= min_word_recall


def _first_hit_rank(doc_ids: list[str], expected: list[str]) -> int | None:
    """1-based rank of the first chunk whose document is expected."""
    return next((i for i, d in enumerate(doc_ids, start=1) if d in expected), None)


def evaluate_pipeline_item(settings: AgentSettings, item: GoldenItem, pipeline: str, use_judge: bool) -> dict[str, Any]:
    """Run one pipeline on one golden item and score it."""
    started = time.time()
    try:
        result = PIPELINES[pipeline](settings, item.store, item.question)
    except Exception as exc:  # noqa: BLE001 - one failure must not stop the batch
        return {"id": item.id, "pipeline": pipeline, "error": f"{type(exc).__name__}: {exc}"[:300]}
    chunk_docs = [c.doc_id for c in result.chunks]
    rank = _first_hit_rank(chunk_docs, item.doc_ids)
    row: dict[str, Any] = {
        "id": item.id, "pipeline": pipeline, "category": item.category, "question_type": item.question_type,
        "hit": rank is not None, "rank": rank, "answerable": result.answerable,
        "golden_match": golden_match(item.answer, result.answer), "latency_s": round(time.time() - started, 1),
        "answer": result.answer,
    }
    if use_judge:
        evidence = "\n".join(f"[{s.source_id}] {s.label}: {s.quote}" for s in result.sources)
        verdict = judge_answer(settings, item.question, result.answer, evidence)
        row.update(judge_overall=verdict.overall, judge_passed=verdict.passed)
    return row


def evaluate_pipelines(settings: AgentSettings, items: Sequence[GoldenItem], pipelines: Sequence[str] = tuple(PIPELINES),
                       use_judge: bool = True, workers: int = 4,
                       progress: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    """Evaluate every pipeline on every item (in parallel threads); returns one row per (item, pipeline)."""
    jobs = [(item, p) for item in items for p in pipelines]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate_pipeline_item, settings, item, p, use_judge) for item, p in jobs]
        for i, future in enumerate(futures, start=1):
            rows.append(future.result())
            if progress:
                row = rows[-1]
                progress(f"[{i}/{len(jobs)}] {row['id']} {row['pipeline']:<11} "
                         + (f"ERROR {row['error']}" if "error" in row else
                            f"hit={row['hit']} match={row['golden_match']} judge={row.get('judge_overall', '-')}"))
    return rows


async def evaluate_graph(service: Any, items: Sequence[GoldenItem], concurrency: int = 2,
                         progress: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    """Ask the full multi-agent graph every item (approval interrupts are auto-rejected) and score the results."""
    semaphore = asyncio.Semaphore(concurrency)

    async def one(item: GoldenItem) -> dict[str, Any]:
        async with semaphore:
            started = time.time()
            try:
                result = await service.ask(item.question, user_id="batch-eval")
                while result.status != "completed":  # evaluation runs unattended
                    value = "reject" if result.status == "needs_approval" else "No further details are available."
                    result = await service.resume(result.thread_id, value)
            except Exception as exc:  # noqa: BLE001
                return {"id": item.id, "pipeline": "graph", "error": f"{type(exc).__name__}: {exc}"[:300]}
            final = result.final
            row = {"id": item.id, "pipeline": "graph", "category": item.category,
                   "question_type": item.question_type, "judge_overall": final.get("score"),
                   "judge_passed": final.get("passed"), "attempts": final.get("attempts"),
                   "agent_calls": final.get("agent_calls"),
                   "hit": any(e.get("ref") in item.doc_ids for e in final.get("evidence", [])),
                   "golden_match": golden_match(item.answer, final.get("answer", "")),
                   "latency_s": round(time.time() - started, 1), "answer": final.get("answer", "")}
            if progress:
                progress(f"{item.id} graph judge={row['judge_overall']} attempts={row['attempts']} "
                         f"match={row['golden_match']} {row['latency_s']}s")
            return row

    return list(await asyncio.gather(*(one(item) for item in items)))


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate rows per pipeline: hit rate, MRR, golden match, judge mean and pass rate, latency."""
    by_pipeline: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pipeline[row["pipeline"]].append(row)
    summary = {}
    for pipeline, group in by_pipeline.items():
        ok = [r for r in group if "error" not in r]
        judged = [r for r in ok if r.get("judge_overall") is not None]

        def mean(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 3) if values else None

        summary[pipeline] = {
            "n": len(group), "errors": len(group) - len(ok),
            "hit_rate": mean([float(r["hit"]) for r in ok]),
            "mrr": mean([1 / r["rank"] if r.get("rank") else 0.0 for r in ok]) if any("rank" in r for r in ok) else None,
            "golden_match": mean([float(r["golden_match"]) for r in ok]),
            "judge_mean": mean([r["judge_overall"] for r in judged]),
            "judge_pass_rate": mean([float(r["judge_passed"]) for r in judged]),
            "latency_mean_s": mean([r["latency_s"] for r in ok]),
        }
    return summary


def save_report(settings: AgentSettings, name: str, items: Sequence[GoldenItem], rows: Sequence[dict[str, Any]],
                summary: dict[str, Any]) -> Path:
    """Write items, rows and summary to ``data/eval/<name>-<timestamp>.json``."""
    settings.eval_dir.mkdir(parents=True, exist_ok=True)
    path = settings.eval_dir / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.json"
    payload = {"name": name, "created": datetime.now().isoformat(timespec="seconds"),
               "judge_model": settings.judge_model, "pass_score": settings.judge_pass_score,
               "items": [asdict(i) for i in items], "summary": summary, "rows": list(rows)}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
