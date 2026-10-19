"""Integrity checks for a generated corpus.

Reads only what is on disk (manifest, PDFs, golden Q&A), so it can be run
independently of a generation run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from data_generation import manifest
from data_generation.qa.pdf_text import page_texts, pages_containing

MIN_DOCS_PER_CATEGORY = 10


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def _has_images(reader: PdfReader) -> bool:
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is None:
            continue
        xobjects = resources.get_object().get("/XObject")
        if xobjects and len(xobjects.get_object()) > 0:
            return True
    return False


def _embeds_fonts(reader: PdfReader) -> bool:
    for page in reader.pages:
        resources = page.get("/Resources")
        fonts = resources.get_object().get("/Font") if resources is not None else None
        for ref in (fonts.get_object().values() if fonts else []):
            descriptor = ref.get_object().get("/FontDescriptor")
            if descriptor and any(k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                return True
    return False


def run(corpus_dir: Path, qa_dir: Path) -> list[Check]:
    checks: list[Check] = []
    try:
        data = manifest.load(corpus_dir)
    except FileNotFoundError:
        return [Check("manifest exists", False, f"{corpus_dir / manifest.MANIFEST_NAME} not found; run generate first")]
    docs = data["documents"]

    paths = {d["doc_id"]: corpus_dir / d["file"] for d in docs}
    missing = [i for i, p in paths.items() if not p.exists()]
    on_disk = {p.resolve() for p in corpus_dir.rglob("*.pdf")}
    extra = sorted(str(p) for p in on_disk - {p.resolve() for p in paths.values()})
    checks.append(Check("manifest matches files on disk", not missing and not extra,
                        f"missing={missing} extra={extra}" if missing or extra else f"{len(paths)} PDFs"))
    if missing:
        return checks

    counts: dict[str, int] = {}
    for d in docs:
        counts[d["category"]] = counts.get(d["category"], 0) + 1
    low = {c: n for c, n in counts.items() if n < MIN_DOCS_PER_CATEGORY}
    checks.append(Check(f"at least {MIN_DOCS_PER_CATEGORY} documents per category", not low, str(counts)))

    out_of_range, with_images, with_fonts = [], [], []
    for d in docs:
        reader = PdfReader(paths[d["doc_id"]])
        lo, hi = d["page_range"]
        if not lo <= len(reader.pages) <= hi:
            out_of_range.append(f"{d['doc_id']}={len(reader.pages)} (expected {lo}-{hi})")
        if _has_images(reader):
            with_images.append(d["doc_id"])
        if _embeds_fonts(reader):
            with_fonts.append(d["doc_id"])
    checks.append(Check("page counts within range", not out_of_range, "; ".join(out_of_range) or "all in range"))
    checks.append(Check("no images or XObjects", not with_images, ", ".join(with_images) or "text only"))
    checks.append(Check("only standard (non-embedded) fonts", not with_fonts, ", ".join(with_fonts) or "core fonts only"))

    unflagged = []
    for d in docs:
        if d["status"] == "superseded":
            first = page_texts(paths[d["doc_id"]], paths[d["doc_id"]].stat().st_mtime)[0]
            if "superseded" not in first:
                unflagged.append(d["doc_id"])
    n_superseded = sum(d["status"] == "superseded" for d in docs)
    checks.append(Check("superseded documents carry a banner", not unflagged,
                        ", ".join(unflagged) or f"{n_superseded} superseded document(s) flagged"))

    qa_path = qa_dir / "golden_qa.jsonl"
    if not qa_path.exists():
        checks.append(Check("golden Q&A exists", False, f"{qa_path} not found"))
        return checks
    items = [json.loads(line) for line in qa_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures = []
    for item in items:
        for source in item["sources"]:
            path = paths.get(source["doc_id"])
            if path is None:
                failures.append(f"{item['id']}: unknown doc {source['doc_id']}")
                continue
            found = pages_containing(path, source["evidence"])
            if not found or not set(source["pages"]) <= set(found) or not source["pages"]:
                failures.append(f"{item['id']}: evidence {source['evidence']} not on pages {source['pages']} of {source['doc_id']}")
    types: dict[str, int] = {}
    for item in items:
        types[item["question_type"]] = types.get(item["question_type"], 0) + 1
    checks.append(Check("golden Q&A evidence found on cited pages", not failures,
                        "; ".join(failures[:5]) + (f" (+{len(failures) - 5} more)" if len(failures) > 5 else "")
                        if failures else f"{len(items)} questions verified {types}"))
    return checks
