# Synthetic RAG teaching corpus - common tasks.
# Every target is a thin wrapper around `uv run`; see TROUBLESHOOTING.md for
# installing `make` on Windows or running the commands directly.

GENERATOR := uv run scripts/corpus_data_generator.py
WORKERS   ?= 6
# Reasoning effort for hybrid runs: none | low | medium | high.
# Empty = use OPENAI_REASONING_EFFORT from .env. Lower effort = faster, cheaper runs.
EFFORT    ?=
LLM_OPTS   = --workers $(WORKERS) $(if $(EFFORT),--effort $(EFFORT),)
# Vector store selection for ingest/validate targets: all | hr | products
STORE     ?= all
# CRM & Support MCP server port on the host
MCP_PORT  ?= 8765
# Evaluation: number of golden questions (empty = EVAL_SAMPLE_SIZE) and GRAPH=1 to include the multi-agent graph
SAMPLE    ?=
GRAPH     ?=

.DEFAULT_GOAL := help
.PHONY: help setup generate generate-fast generate-template generate-hr generate-products refresh verify clean clean-cache \
        ingest ingest-reset validate-stores validate-stores-offline clean-stores \
        mcp-server-up mcp-server-down mcp-server-logs mcp-server-status mcp-seed-reset crm-seed \
        sync-skills check-skills evaluate evaluate-fast graph-diagram clean-agent-state

help: ## Show available targets
	@uv run python -c "import re; [print(f'  {m[0]:<25} {m[1]}') for m in re.findall(r'^([a-z-]+):.*?## (.*)$$', open('Makefile').read(), re.M)]"

setup: ## Create the .venv and install dependencies (uv sync)
	uv sync

generate: ## Generate the full corpus (hybrid if OPENAI_API_KEY is set); e.g. make generate EFFORT=low
	$(GENERATOR) generate $(LLM_OPTS)

generate-fast: ## Fastest hybrid run: low reasoning effort, 10 parallel requests
	$(GENERATOR) generate --mode hybrid --effort low --workers 10

generate-template: ## Generate the full corpus offline, without the LLM
	$(GENERATOR) generate --mode template

generate-hr: ## Generate HR policies only (hybrid)
	$(GENERATOR) generate --mode hybrid --only hr $(LLM_OPTS)

generate-products: ## Generate product manuals only (hybrid)
	$(GENERATOR) generate --mode hybrid --only products $(LLM_OPTS)

refresh: ## Regenerate all LLM prose, ignoring the cache; e.g. make refresh EFFORT=medium
	$(GENERATOR) generate --mode hybrid --refresh $(LLM_OPTS)

verify: ## Verify the corpus on disk (page counts, no images, golden Q&A evidence)
	$(GENERATOR) verify

clean: ## Delete generated PDFs and golden Q&A (keeps the LLM cache)
	uv run python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('data/corpus', 'data/golden_qa')]"

clean-cache: ## Delete the LLM cache (next hybrid run calls the API again)
	uv run python -c "import shutil; shutil.rmtree('data/cache', ignore_errors=True)"

ingest: ## Embed corpus PDFs into the Chroma stores (unchanged docs skipped); e.g. make ingest STORE=hr
	uv run scripts/ingest_vector_stores.py --store $(STORE)

ingest-reset: ## Empty and rebuild the Chroma store(s) from scratch
	uv run scripts/ingest_vector_stores.py --store $(STORE) --reset

validate-stores: ## Summarise the vector stores, cross-check the manifest and run sample queries
	uv run scripts/validate_vector_stores.py --store $(STORE)

validate-stores-offline: ## Same as validate-stores without sample queries (no API calls)
	uv run scripts/validate_vector_stores.py --store $(STORE) --skip-queries

clean-stores: ## Delete both Chroma databases (data/vectorstores)
	uv run python -c "import shutil; shutil.rmtree('data/vectorstores', ignore_errors=True)"

mcp-server-up: ## Build and start the CRM & Support MCP server in Docker (localhost only)
	docker compose up -d --build crm-mcp
	@echo "CRM & Support MCP server: http://localhost:$(MCP_PORT)/mcp   (logs: make mcp-server-logs)"

mcp-server-down: ## Stop and remove the MCP server container (data in data/crm is kept)
	docker compose down

mcp-server-logs: ## Follow the MCP server logs (shows the colourful startup banner)
	docker compose logs -f crm-mcp

mcp-server-status: ## Check the MCP server /health endpoint
	@uv run python -c "import urllib.request as u; print(u.urlopen('http://localhost:$(MCP_PORT)/health', timeout=3).read().decode())" || echo "MCP server is not reachable on port $(MCP_PORT)"

mcp-seed-reset: ## Delete all CRM data in the running container and reload the seed
	docker compose exec crm-mcp python -m mcp_servers.crm_support --reset-seed

crm-seed: ## Regenerate the CRM seed JSON from the corpus catalog
	uv run scripts/build_crm_seed.py

sync-skills: ## Mirror src/skills to .claude/skills (Claude Code, Copilot) and .agents/skills (Codex, Copilot)
	uv run scripts/sync_skills.py sync

check-skills: ## Validate skill frontmatter and fail if the mirrors drifted from src/skills
	uv run scripts/sync_skills.py check

evaluate: ## Sampled evaluation of the RAG pipelines with the judge; e.g. make evaluate SAMPLE=10 GRAPH=1
	uv run scripts/evaluate_rag.py $(if $(SAMPLE),--sample $(SAMPLE),) $(if $(GRAPH),--graph,)

evaluate-fast: ## Retrieval-only evaluation (hit rate, MRR, golden match) without judge calls
	uv run scripts/evaluate_rag.py --no-judge $(if $(SAMPLE),--sample $(SAMPLE),)

graph-diagram: ## Export the Coordinator graph as Mermaid to docs/diagrams/coordinator_graph.mmd
	uv run scripts/export_graph_diagram.py

clean-agent-state: ## Delete short-term (checkpoints) and long-term (user facts) agent memory
	uv run python -c "import shutil; shutil.rmtree('data/agent_state', ignore_errors=True)"
