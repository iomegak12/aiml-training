# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - multi-agent RAG
- **`src/agentic_rag`** package:
  - **Retrieval:** Chroma stores, metadata filters with model, document and version inference, vector + MMR search,
    BM25 and hybrid Reciprocal Rank Fusion.
  - **Pipelines:** four RAG pipelines (hybrid, advanced, multi-query, corrective) with a groundedness check and an
    honest "I don't know".
  - **Web:** Serper web search.
  - **Judge:** the judge LLM gate, scoring four criteria with a weighted overall score.
  - **Memory:** SQLite short-term and long-term memory.
  - **MCP:** MCP tool loading.
- **Specialist Deep Agents** (HR Policy, Product Manuals, Customer Support, Ticket Management, Research):
  - Each has only its own tools and read-only skills.
  - Each returns a structured `AgentReport`.
  - Ticket writes are *proposed*, never executed by an agent.
- **Coordinator graph** (LangGraph):
  - plan, with an optional clarifying interrupt
  - parallel `Send` dispatch with dependencies
  - reflect and replan
  - human approval interrupt
  - execute approved MCP writes
  - synthesize
  - judge with targeted retries and a low-confidence fallback
  - long-term memory
- `CoordinatorService` (`ask` / `resume`, live progress, Markdown rendering in notebooks).
- **CRM & Support MCP server** (`src/mcp_servers/crm_support`): FastMCP over streamable HTTP with SQLite.
  - 6 tools, 5 resources and 2 prompts.
  - Business rules and a duplicate guard.
  - A seed of 40 customers and 120 tickets built from the corpus catalogue.
  - A coloured startup banner and a `/health` route.
- `Dockerfile` (multi-stage, slim trixie base, non-root, no HEALTHCHECK), `docker-compose.yml` (published on
  127.0.0.1 only) and `.dockerignore` (whitelist).
- Seven Agent Skills in `src/skills`, mirrored to `.claude/skills` and `.agents/skills` by
  `scripts/sync_skills.py`, with a drift and frontmatter check.
- `scripts/evaluate_rag.py`: sampled evaluation with hit rate, MRR, golden-answer key-fact match, judge score and
  latency.
- `scripts/export_graph_diagram.py`: Mermaid export of the compiled graph.
- Twelve scenario notebooks in `notebooks/`, delivered without outputs.
- `docs/architecture/multi_agent_architecture.md` with Mermaid diagrams.
- `config/mcp_servers.json`.
- Makefile targets:
  - `mcp-server-up`, `mcp-server-down`, `mcp-server-logs`, `mcp-server-status`, `mcp-seed-reset`, `crm-seed`
  - `sync-skills`, `check-skills`
  - `evaluate`, `evaluate-fast`
  - `graph-diagram`, `clean-agent-state`
- New `.env` keys for the models and reasoning efforts, graph budgets, judge thresholds, retrieval settings,
  Serper, state paths and the MCP server.

### Added
- `EFFORT` and `WORKERS` variables for every hybrid Makefile target, and a `make generate-fast` target
  (`--effort low --workers 10`).
- Measured speed table for each reasoning effort in the README.
- **Pre-RAG ingestion:** a `src/data_ingestion` package and `scripts/ingest_vector_stores.py`.
  - The pipeline loads PDFs page by page, cleans the text, splits it with `RecursiveCharacterTextSplitter`,
    builds metadata, embeds with `OpenAIEmbeddings`, and writes two persistent Chroma databases (`hr_policies`,
    `product_manuals`).
  - Chunk sizes, batch sizes and header stripping are configured in `.env`.
  - Re-runs are idempotent: unchanged documents are skipped and deleted PDFs are removed from the store.
- `scripts/validate_vector_stores.py` shows the summary and build config, statistics, metadata coverage, sample
  records, a manifest cross-check and sample similarity queries.
- Makefile targets `ingest`, `ingest-reset`, `validate-stores`, `validate-stores-offline` and `clean-stores`.
- `.env.example` documenting every setting.
- Mermaid architecture diagrams in `docs/architecture/pre_rag_architecture.md`.

### Fixed
- PDF outline bookmarks pointed to page 1. They are now registered when their page is written.
- List bullets extracted as a control character (`\x7f`). Lists now use a plain `-` marker.

### Changed
- The LLM cache key no longer includes the reasoning effort. Switching effort reuses cached prose, and only
  `--refresh` requests sections again.
- LLM output is normalised to plain ASCII punctuation before the guard and rendering run.

## [0.1.0] - 2026-10-19

### Added
- `scripts/corpus_data_generator.py` orchestrator with `generate` and `verify` commands.
- `src/data_generation` helper package: catalog, builders, LLM enrichment, PDF rendering, golden Q&A, manifest and verification.
- 15 product manuals (8 TVs, 7 mobile phones) for four fictional brands, each 5 to 10 pages.
- 15 HR policy documents for a fictional Indian employer, each 3 to 4 pages, including 2 superseded versions.
- Hybrid mode: OpenAI Responses API prose enrichment with a JSON cache and a number and sibling-model guard.
- Deterministic golden Q&A set (JSONL and CSV) with evidence strings and page numbers, verified against the PDFs.
- Corpus manifest with metadata for filtering (brand, model, family, version, status, effective date).
- Automatic page-range fitting through layout densities.
- Makefile, README, TROUBLESHOOTING, SECURITY, CODE_OF_CONDUCT and MIT LICENSE.
