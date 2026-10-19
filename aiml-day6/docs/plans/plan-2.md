# Plan: Pre-RAG Ingestion into Two Chroma Vector Databases (aiml-day6)

## Context
The synthetic corpus now exists: 30 text-only PDFs in `data/corpus/`, a `manifest.json` with rich metadata, and a golden Q&A set. The next teaching step is the pre-RAG pipeline described in the LangChain docs (`deepagents/retrieval`, then the semantic-search tutorial and the Chroma integration page): **load PDFs, apply size-based chunking, generate metadata, embed with OpenAI, and store in Chroma**. There are two separate vector databases, one for HR and compliance documents and one for product manuals and guides, plus a validation script that summarises what each store contains.

Decisions agreed in the MCQ rounds:
- **Stack:** LangChain components: `langchain-text-splitters`, `langchain-openai` and `langchain-chroma`.
- **Two local persistent Chroma databases:** `data/vectorstores/hr_policies/` and `data/vectorstores/product_manuals/`.
- **Chunk size per store, in characters,** configured in `.env`.
- **Page-level split:** one Document per page, so chunks never cross pages.
- **Metadata:** common PDF fields, plus corpus manifest fields, chunk lineage and structure hints.
- **Two batch knobs in `.env`:**
  - `INGEST_BATCH_SIZE`: the number of PDFs processed in parallel.
  - `EMBEDDING_BATCH_SIZE`: the number of chunks per embeddings request and per Chroma write.
- **Re-runs are idempotent:** deterministic chunk IDs and a per-document replace. `--reset` rebuilds a store.
- **Header and footer stripping:** configurable with `STRIP_HEADERS_FOOTERS=true` (on by default).
- **Code layout:** a new `src/data_ingestion/` package plus two thin scripts. Every new module, class and function gets a docstring.
- **Validation:** counts and config, distribution and stats, sample records, a manifest cross-check, and 2 or 3 sample queries per store.

## Configuration (`.env`; values are also documented in a new `.env.example`)
```dotenv
OPENAI_EMBEDDING_MODEL=text-embedding-3-small   # already present
VECTORSTORE_DIR=data/vectorstores
HR_COLLECTION_NAME=hr_policies
PRODUCT_COLLECTION_NAME=product_manuals
HR_CHUNK_SIZE=800
HR_CHUNK_OVERLAP=120
PRODUCT_CHUNK_SIZE=1200
PRODUCT_CHUNK_OVERLAP=200
INGEST_BATCH_SIZE=4          # PDFs loaded/cleaned/chunked in parallel
EMBEDDING_BATCH_SIZE=100     # chunks per embeddings request and Chroma upsert
STRIP_HEADERS_FOOTERS=true
VALIDATION_SAMPLE_SIZE=3
```
- Only these non-secret keys are appended to `.env`. Existing lines stay untouched.
- The code has the same defaults, so a missing key still works.
- `.gitignore` gets `!.env.example`, because `.env.*` is currently ignored, and `data/vectorstores/`.

## Package layout: `src/data_ingestion/`
This mirrors `data_generation`: small modules, each with module, class and function docstrings.

| Module | Responsibility |
|---|---|
| `config.py` | `StoreConfig` (name, category, source dir, persist dir, collection, chunk size and overlap) and `IngestionSettings.load(root)`, which reads `.env` via python-dotenv. Two stores are defined: `hr` (category `hr_policy`, source `data/corpus/hr_policies`) and `products` (category `product_manual`, source `data/corpus/product_manuals`). |
| `loading.py` | `load_pdf_pages(path) -> list[Document]`: one LangChain `Document` per page using `pypdf`, the same pattern as the tutorial. Adds the **common PDF metadata**. |
| `cleaning.py` | `strip_headers_footers(pages)`: a generic, frequency-based remover. It drops lines that repeat on at least 60% of a document's pages, and `Page X of Y` patterns. It isn't tied to this renderer, so it works on any PDF. |
| `structure.py` | `section_index(path)` reads the PDF outline (our PDFs have H1 bookmarks) to get `section_title` per chunk position, falling back to the previous page's last heading. `classify_content(text)` labels `table`, `list` or `prose` heuristically, using the share of short lines and bullet or number prefixes. |
| `chunking.py` | `build_splitter(cfg)` returns `RecursiveCharacterTextSplitter(chunk_size, chunk_overlap, add_start_index=True)`. `split_pages(pages, splitter)` splits page by page. |
| `metadata.py` | `ManifestIndex` maps file names to manifest records, reusing `data_generation.manifest.load()`. `build_chunk_metadata(...)` merges the field groups listed below. `sanitize_for_chroma(meta)` drops `None` values, joins lists with commas and keeps only str, int, float or bool, because Chroma rejects other types. |
| `embeddings.py` | `make_embeddings(settings)` returns `OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL, chunk_size=EMBEDDING_BATCH_SIZE)`. |
| `vectorstore.py` | `open_store(cfg, embeddings)` returns `langchain_chroma.Chroma(collection_name, embedding_function, persist_directory, collection_metadata=…)`. Also `reset_store`, `replace_document_chunks(store, doc_id, docs, ids, batch)` (delete `where doc_id`, then `add_documents` in batches), and read helpers for validation (`collection.count()`, `get(include=…)`). Collection metadata records `embedding_model`, `embedding_dimensions`, `chunk_size`, `chunk_overlap`, `strip_headers_footers`, `pipeline_version`, `ingested_at` and cosine distance. |
| `pipeline.py` | `process_pdf(path, cfg, manifest)` runs load, clean, structure, chunk and metadata, and returns the chunks plus IDs. `ingest_store(cfg, settings, reset)` discovers PDFs, processes them in a `ThreadPoolExecutor(INGEST_BATCH_SIZE)`, then embeds and upserts per document in `EMBEDDING_BATCH_SIZE` batches. It returns an `IngestReport` with per-document pages and chunks, totals and timing. |
| `validation.py` | `summarize_store(cfg)`: counts, config, distinct documents, chunks per document, chunk length min/avg/max, `content_type` mix and per-field metadata coverage. `sample_records(cfg, n)`: ID, text preview, metadata, embedding dimension and the first values. `cross_check_manifest(cfg, manifest)`: missing or extra documents, documents in the wrong store, and page-count mismatches. `run_sample_queries(cfg, embeddings, k)`: 2 or 3 fixed queries per store, with top-k results showing doc ID, page, section and score. All functions return dataclasses; the scripts do the printing. |

### Chunk metadata
- **Common PDF metadata (always):** `source` (relative path), `file_name`, `file_size_bytes`, `page` (0-based, the LangChain convention), `page_number` (1-based, for citations and the golden Q&A), `total_pages`, `pdf_title`, `pdf_author`, `pdf_subject`, `pdf_keywords` and `pdf_creator`.
- **Corpus manifest fields:** `doc_id`, `category`, `subcategory`, `title`, `publisher`, `brand`, `model`, `model_number`, `family`, `version`, `status` (current or superseded), `effective_date`, `supersedes` and `superseded_by`. PDFs that aren't in the manifest still ingest; their `doc_id` comes from the file name.
- **Chunk lineage:**
  - `chunk_id` is deterministic: `{doc_id}:p{page:03d}:c{index:02d}`.
  - `chunk_index` (within the page) and `chunk_index_in_doc`.
  - `chunks_in_doc` and `start_index`.
  - `char_count` and `token_count` (tiktoken, which `langchain-openai` already depends on).
  - `content_hash` (SHA-256, first 16 characters).
- **Structure hints:** `section_title` and `content_type` (`table`, `list` or `prose`).

## Scripts (thin orchestrators, like `corpus_data_generator.py`)
- `scripts/ingest_vector_stores.py [--store all|hr|products] [--reset]` prints a per-document table (pages, chunks, section coverage), the totals per store, and the elapsed time.
- `scripts/validate_vector_stores.py [--store all|hr|products] [--samples N] [--k 3] [--skip-queries]` prints, for each store: summary and config, distribution and statistics, sample records, the manifest cross-check (PASS/FAIL), and the sample queries. It exits non-zero if a cross-check fails.

## Other changes
- **Dependencies:** `uv add langchain-core langchain-text-splitters langchain-openai langchain-chroma`. `chromadb` and `tiktoken` come in transitively.
- **Makefile:** `ingest`, `ingest-reset` and `validate-stores` (all with `STORE=`), plus `validate-stores-offline` (`--skip-queries`).
- **Docs:**
  - README gets a "Pre-RAG: vector stores" section: pipeline diagram (text), `.env` keys, a metadata table with the recommendations and why, and how to run.
  - TROUBLESHOOTING gets Chroma and embedding issues: a locked DB on Windows, metadata type errors, a changed chunk size needing `--reset`, and rate limits.
  - CHANGELOG `[Unreleased]` entry.
- **Memory:** update the project memory with the ingestion design.

## Verification
1. Run `uv sync`, then `uv run scripts/ingest_vector_stores.py --reset`. Expect both stores to be created, with 15 documents each, and the chunk counts printed. The cost is tiny: about 150k tokens with `text-embedding-3-small`.
2. Run `uv run scripts/ingest_vector_stores.py` again. Record counts must stay identical, which shows the idempotent upsert.
3. Run `uv run scripts/validate_vector_stores.py`:
   - The manifest cross-check passes, with 15 HR and 15 product documents in the correct stores and matching page counts.
   - Metadata coverage is 100% for the common, manifest and lineage fields.
   - Sample records show 1,536-dimension embeddings.
   - The sample queries return the expected documents, for example the earned-leave query returns `HR-POL-001-V3.0`.
4. Change `HR_CHUNK_SIZE`, run `ingest --store hr --reset`, and check that the validation shows the new chunk size in the collection config and a different chunk count.
5. Set `STRIP_HEADERS_FOOTERS=false`, re-ingest and validate. The sample records should now contain the "Page X of Y" header noise. This is the demonstration of why cleaning matters.
