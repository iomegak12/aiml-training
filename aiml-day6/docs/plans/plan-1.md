# Plan: Synthetic RAG Teaching Corpus Generator (aiml-day6)

## Context
Ramkumar needs a realistic, text-only document set to show students a range of RAG techniques: chunking tables, metadata filtering, recency and conflict handling, and evaluation. The project at `C:\000-AIML\demonstrations\aiml-day6` is a fresh `uv` scaffold (Python 3.12.10, empty `data/` and `scripts/`, no dependencies, plus a placeholder `main.py`). `.env` already holds `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-5.1` and `OPENAI_REASONING_EFFORT=high`.

Decisions agreed in the MCQ rounds:
- **Hybrid content.** Python templates and catalogs own all facts. Optionally, OpenAI expands the prose, and its output is cached to JSON.
- **Fictional brands.** An Indian HR context (INR, Indian statutes).
- **PDF only**, rendered with ReportLab. Text only, with no images or diagrams.
- **15 product manuals** (8 TVs and 7 phones, 5–10 pages each) and **15 HR documents** (3–4 pages each).
- **RAG traps:** text tables, near-duplicate models, versioned or conflicting documents, and a golden Q&A set.
- **Structure:**
  - Delete `main.py` from the root.
  - All helper source code lives in `src/data_generation/`.
  - `scripts/corpus_data_generator.py` only imports those helpers and coordinates the run.
- **Repo housekeeping files:** README, .gitignore, Makefile, TROUBLESHOOTING, CODE_OF_CONDUCT, an MIT LICENSE (Copyright (c) 2026 Ramkumar <jd.ramkumar@gmail.com>), CHANGELOG and SECURITY, plus `.gitkeep` in `scripts/` and `data/`.

## Project layout
```
aiml-day6/
  pyproject.toml            # deps + hatchling build so `data_generation` is importable (src layout)
  .gitignore                # existing + .env, data/cache/, data/corpus/, data/golden_qa/
  Makefile                  # setup | generate | generate-template | generate-hr | generate-products | refresh | verify | clean
  README.md                 # overview, quick start, CLI, corpus inventory, RAG-traps cheat-sheet
  TROUBLESHOOTING.md        # uv/Python issues, OpenAI auth/rate limits, `make` on Windows, page-count drift, cache resets
  CODE_OF_CONDUCT.md        # Contributor Covenant 2.1, contact jd.ramkumar@gmail.com
  LICENSE                   # MIT, Copyright (c) 2026 Ramkumar <jd.ramkumar@gmail.com>
  CHANGELOG.md              # Keep a Changelog format, 0.1.0 initial release
  SECURITY.md               # never commit .env, key rotation, reporting a vulnerability
  scripts/
    .gitkeep
    corpus_data_generator.py   # orchestrator only: parse args -> build -> enrich -> render -> Q&A -> verify -> summary
  src/data_generation/
    __init__.py
    config.py               # Settings dataclass: loads .env (python-dotenv), paths, defaults
    models.py               # dataclasses: Document(meta, sections), Section, Paragraph, Bullets, Table, Notice
    catalog/
      __init__.py
      products.py           # 15 product spec dicts (every fact/number lives here)
      hr_policies.py        # company profile + 15 policy fact dicts
    builders/
      __init__.py           # build_all(only=...) -> list[Document]
      tv_manual.py          # facts -> Document (template prose)
      phone_manual.py
      hr_policy.py
    llm/
      __init__.py
      client.py             # OpenAI Responses API wrapper, retry/backoff
      cache.py              # JSON cache keyed by hash(prompt, model, effort)
      guard.py              # number / model-name guard
      enricher.py           # enrich(documents, workers, refresh) -> stats
    rendering/
      __init__.py
      pdf_renderer.py       # ReportLab: Document -> PDF (+ NumberedCanvas, styles)
    qa/
      __init__.py
      golden_qa.py          # deterministic Q&A from facts + pypdf page mapping
    manifest.py             # write data/corpus/manifest.json
    verify.py               # corpus integrity checks -> report
data/
  .gitkeep
  corpus/product_manuals/tv/*.pdf
  corpus/product_manuals/mobile/*.pdf
  corpus/hr_policies/*.pdf
  corpus/manifest.json
  golden_qa/golden_qa.jsonl + golden_qa.csv
  cache/llm/<doc_id>/<section_id>.json
```

**Packaging.** Add `[build-system]` (hatchling) and `[tool.hatch.build.targets.wheel] packages = ["src/data_generation"]` to `pyproject.toml`. `uv sync` then installs the package in editable mode, so the script can simply `from data_generation import ...` with no `sys.path` hacks.

## Orchestrator (`scripts/corpus_data_generator.py`)
This file stays thin, at about 100 lines, and contains no content or rendering logic. Its subcommands:
```
uv run scripts/corpus_data_generator.py generate [--mode template|hybrid] [--only products|hr]
                                                 [--refresh] [--effort low|medium|high] [--workers N]
uv run scripts/corpus_data_generator.py verify
```
The `generate` flow:
1. `Settings.load()`
2. `builders.build_all(only)`
3. If the mode is hybrid: `llm.enricher.enrich(docs, ...)`
4. `rendering.render_all(docs, out_dir)`
5. `manifest.write(...)`
6. `qa.golden_qa.generate(...)`
7. `verify.run(...)`
8. Print a summary table.

## Corpus content

**Fictional brands:**
- TVs: **Voltara** and **Lumenix**.
- Phones: **Nexora** and **Zentrix**.
- Employer: **Aranya Technologies Pvt. Ltd.**, headquartered in Bengaluru.

**TVs (8), including near-duplicate families:**
- Voltara Lumina 43 / 55 / 55 Pro / 65 Pro.
- Lumenix QLED Q50 / Q55 / Q55X / OLED O65.
- Siblings differ in a few values only: refresh rate, HDMI 2.1 port count, speaker wattage, warranty period and error codes.

**Phones (7), including near-duplicate families:**
- Nexora Aria 12 Lite / 12 / 12 Pro.
- Zentrix Z9 / Z9 Plus / Z9 Ultra / Z5.
- Siblings differ in battery capacity, charging wattage, IP rating, camera MP and SAR values.

**Manual sections** (the template-only output already reaches 5–10 pages):
1. Safety instructions.
2. Box contents.
3. Product overview: buttons and ports, described in text.
4. Installation or setup.
5. First-time setup.
6. Feature guide.
7. Connectivity.
8. Settings menu reference.
9. Care and maintenance.
10. Troubleshooting table (about 15–20 rows).
11. Error-code table.
12. Technical specifications table.
13. Warranty and service in India.
14. Regulatory: BIS, E-Waste Rules 2022, SAR.
15. Support contacts.

**HR documents (15).** These comprise 13 current policies plus 2 superseded versions, which form the conflict traps:
1. Leave Policy v3.0, 2025 (current).
2. Leave Policy v2.0, 2023 (**SUPERSEDED**).
3. Travel & Expense Claims Policy v2026 (current).
4. Travel & Expense Claims Policy v2024 (**SUPERSEDED**).
5. Medical Reimbursement & Group Health Insurance.
6. Code of Conduct & Ethics.
7. POSH (Act 2013).
8. Hybrid Work / WFH.
9. IT Acceptable Use & InfoSec.
10. Data Privacy (DPDP Act 2023).
11. Attendance, Working Hours & Overtime.
12. Performance Management & Appraisal.
13. Whistleblower & Grievance Redressal.
14. Anti-Bribery & Anti-Corruption.
15. Separation, Notice Period & F&F (Gratuity).

**Shape of each HR document:**
- Document-control block: ID, version, owner, effective date, status, and "supersedes" or "superseded by".
- Purpose, Scope, Definitions, Policy, Procedure and Exceptions sections.
- An entitlement or limit table.
- FAQs and a revision history.
- Superseded documents also carry a text "SUPERSEDED" banner.

## Hybrid generation (`src/data_generation/llm/`)
- **Mode flag:** `--mode template|hybrid`. The default is `hybrid` when `OPENAI_API_KEY` is set, otherwise `template`.
- **What goes to the LLM.** Only prose paragraphs are sent. Tables, specs, numbers and document-control blocks always come from the catalogs.
- **API call.** `client.responses.create(model=OPENAI_MODEL, reasoning={"effort": OPENAI_REASONING_EFFORT}, ...)`. A `--effort` CLI flag overrides the effort.
- **Guard.** Every numeric token in the LLM output must appear in the facts or the template draft. Sibling model names are rejected. If either check fails, the section falls back to the template text and the rejection is logged. This keeps the golden Q&A valid.
- **Cache and throughput.** Results are cached to `data/cache/llm/...` and `--refresh` regenerates them. Calls run through a `ThreadPoolExecutor` (default 6 workers) with retry and backoff. That's about 300 calls one time, then 0 on reruns.

## PDF rendering (`src/data_generation/rendering/pdf_renderer.py`)
- **Page building:** ReportLab Platypus (Paragraph, grid-styled Table, ListFlowable).
- **Header and footer:** doc ID, version, and "Page X of Y" via `NumberedCanvas`.
- **PDF metadata:** title, author, subject and keywords (doc ID, version, status).
- **Content constraints:** core fonts only, with no images, drawings or XObjects. "Rs." is used in place of "₹".

## Golden Q&A (`src/data_generation/qa/golden_qa.py`)
- **Source.** About 200 questions, generated **deterministically from the catalog facts**.
- **Fields:** `id`, `question`, `answer`, `category`, `question_type`, `source_doc`, `source_pages`, `evidence`, `difficulty`.
- **Question types:** `factual`, `table_lookup`, `near_duplicate`, `version_conflict` (the superseded value is noted as a distractor), `comparison`, `procedural`, `unanswerable`.
- **Page mapping.** `pypdf` extracts each page's text, the `evidence` string is located on its page, and `source_pages` is filled from that.

## Makefile
The targets wrap the `uv run` commands: `setup` (`uv sync`), `generate`, `generate-template`, `generate-hr`, `generate-products`, `refresh`, `verify` and `clean` (removes the generated corpus and Q&A, keeps the cache). TROUBLESHOOTING.md explains how to get `make` on Windows (`choco install make` or `winget install GnuWin32.Make`) and lists the raw `uv run` equivalents.

## Implementation steps
1. Delete `main.py`. Update `pyproject.toml` (description, hatchling build, src package) and run `uv add reportlab openai python-dotenv pypdf`.
2. Add `.env`, `data/cache/`, `data/corpus/` and `data/golden_qa/` to `.gitignore` (`.env` is currently **not** ignored). Add `scripts/.gitkeep` and `data/.gitkeep`.
3. Build `src/data_generation/` module by module: config and models, then catalogs, builders, rendering, LLM, Q&A, manifest and verify.
4. Write the thin `scripts/corpus_data_generator.py` orchestrator.
5. Write the Makefile, README, TROUBLESHOOTING, CODE_OF_CONDUCT, LICENSE, CHANGELOG and SECURITY files.

## Verification
1. Run `uv sync`, then `uv run scripts/corpus_data_generator.py generate --mode template`. This is offline and should produce 30 PDFs, with manuals at 5–10 pages and HR documents at 3–4.
2. `uv run scripts/corpus_data_generator.py verify` asserts the following:
   - The page ranges are as expected.
   - No page has image XObjects.
   - Every Q&A evidence string appears on its `source_pages`.
   - The manifest matches the files on disk.
   - Superseded documents contain the banner.
3. `generate --mode hybrid --only hr` uses real OpenAI calls. Inspect the cache and the guard rejections, then rerun to confirm 0 API calls (all cache hits).
4. Run the full hybrid generation and `verify`. Open a TV manual, a phone manual and a superseded policy to check them visually.
