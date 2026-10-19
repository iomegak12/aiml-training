"""Hybrid mode: expand template prose with an LLM, section by section.

Only paragraphs marked ``enrich=True`` are sent to the model. Tables, lists,
specifications and policy rules are never touched. Every rewrite passes
through ``guard.check``; rejected rewrites keep the template text.
"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from data_generation.llm.cache import LLMCache, cache_key
from data_generation.llm.client import LLMClient
from data_generation.llm.guard import check
from data_generation.models import Bullets, Document, Notice, Paragraph, Section, Subheading, Table

INSTRUCTIONS = """You are a senior technical writer producing realistic documentation for a teaching dataset.
Rewrite the DRAFT text for one section of a document so it reads like a polished, professional publication.

Strict rules:
- Use ONLY information found in FACTS, CONTEXT or DRAFT. Do not invent features, rules, products or names.
- Do not write any number, quantity, price, percentage or date unless it appears in FACTS, CONTEXT or DRAFT.
- Never mention any other product model, product family member or policy version than the one named.
- Write plain prose paragraphs separated by one blank line. No headings, bullet points, numbering or markdown.
- Use Indian English spelling and a clear, helpful tone suitable for {audience}.
- Length: {paragraphs} paragraph(s), {min_words} to {max_words} words in total."""

PROFILES = {
    "product_manual": {"audience": "consumers in India", "paragraphs": "2", "min_words": 60, "max_words": 100},
    "hr_policy": {"audience": "employees of an Indian technology company", "paragraphs": "1 to 2",
                  "min_words": 50, "max_words": 90},
}


@dataclass
class EnrichmentStats:
    sections: int = 0
    api_calls: int = 0
    cache_hits: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: int = 0
    rejections: list[dict] = field(default_factory=list)
    per_doc_accepted: Counter = field(default_factory=Counter)

    def as_dict(self) -> dict:
        return {
            "sections": self.sections, "api_calls": self.api_calls, "cache_hits": self.cache_hits,
            "accepted": self.accepted, "rejected": self.rejected, "errors": self.errors,
            "rejections": self.rejections,
        }


# Typographic characters LLMs like to emit; several (e.g. U+2011) are missing from the PDF core fonts.
_TYPOGRAPHY = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": " - ", "―": " - ",
    " ": " ", " ": " ", " ": " ", "…": "...",
})


def normalize_typography(text: str) -> str:
    return text.translate(_TYPOGRAPHY)


def _block_text(block) -> str:
    match block:
        case Paragraph() | Subheading() | Notice():
            return block.text
        case Bullets():
            return "\n".join(block.items)
        case Table():
            rows = ([block.header] if block.header else []) + block.rows
            return "\n".join(" | ".join(r) for r in rows)
    return ""


def _identity(doc: Document) -> str:
    m = doc.meta
    if m.category == "product_manual":
        return f"{m.brand} {m.model} (model number {m.model_number}) user manual"
    return f"{m.title} version {m.version}, effective {m.effective_date}, {m.publisher}"


def _prompt(doc: Document, section: Section) -> tuple[str, str, str]:
    """Returns (instructions, prompt, allowed_text_for_guard)."""
    draft = "\n\n".join(b.text for b in section.blocks if isinstance(b, Paragraph) and b.enrich)
    context = "\n".join(_block_text(b) for b in section.blocks if not (isinstance(b, Paragraph) and b.enrich))
    facts = json.dumps(section.facts, ensure_ascii=False, default=str)
    instructions = INSTRUCTIONS.format(**PROFILES[doc.meta.category])
    prompt = (f"DOCUMENT: {_identity(doc)}\nSECTION: {section.title}\n\nFACTS (JSON):\n{facts}\n\n"
              f"CONTEXT (rest of this section, for consistency only - do not repeat it):\n{context[:2500]}\n\n"
              f"DRAFT:\n{draft}")
    allowed = "\n".join([_identity(doc), section.title, facts, context, draft])
    return instructions, prompt, allowed


def _apply(section: Section, text: str) -> None:
    paragraphs = [Paragraph(p.strip()) for p in text.split("\n\n") if p.strip()]
    blocks, inserted = [], False
    for block in section.blocks:
        if isinstance(block, Paragraph) and block.enrich:
            if not inserted:
                blocks.extend(paragraphs)
                inserted = True
            continue
        blocks.append(block)
    section.blocks = blocks


def enrich(docs: list[Document], client: LLMClient, cache: LLMCache, refresh: bool = False, workers: int = 6,
           progress=print) -> EnrichmentStats:
    stats = EnrichmentStats()
    jobs = [(doc, section) for doc in docs for section in doc.sections
            if any(isinstance(b, Paragraph) and b.enrich for b in section.blocks)]
    stats.sections = len(jobs)

    def run(doc: Document, section: Section):
        instructions, prompt, allowed = _prompt(doc, section)
        key = cache_key(client.model, instructions, prompt)
        output = None if refresh else cache.get(doc.meta.doc_id, section.id, key)
        from_cache = output is not None
        if output is None:
            output = client.complete(instructions, prompt)
            cache.put(doc.meta.doc_id, section.id, key, client.model, client.reasoning_effort, prompt, output)
        output = normalize_typography(output)
        ok, reason = check(output, allowed, doc.meta.model, doc.meta.sibling_models)
        return output, from_cache, ok, reason

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(run, doc, section): (doc, section) for doc, section in jobs}
        for done, future in enumerate(as_completed(futures), start=1):
            doc, section = futures[future]
            try:
                results[(doc.meta.doc_id, section.id)] = future.result()
            except Exception as exc:  # noqa: BLE001 - any API failure falls back to template text
                stats.errors += 1
                stats.rejections.append({"doc_id": doc.meta.doc_id, "section": section.id, "reason": f"error: {exc}"})
            if done % 25 == 0 or done == len(jobs):
                progress(f"  LLM enrichment: {done}/{len(jobs)} sections processed")

    for doc, section in jobs:
        result = results.get((doc.meta.doc_id, section.id))
        if result is None:
            continue
        output, from_cache, ok, reason = result
        stats.cache_hits += from_cache
        stats.api_calls += not from_cache
        if ok:
            _apply(section, output)
            stats.accepted += 1
            stats.per_doc_accepted[doc.meta.doc_id] += 1
        else:
            stats.rejected += 1
            stats.rejections.append({"doc_id": doc.meta.doc_id, "section": section.id, "reason": reason})
    return stats
