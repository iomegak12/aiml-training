# Pre-RAG Architecture: from PDFs to Two Chroma Vector Databases

This document describes how the pre-RAG components in `src/data_ingestion/` work together to turn the
generated PDF corpus into two persistent Chroma vector databases:
- `hr_policies` holds HR and compliance documents.
- `product_manuals` holds product manuals and guides.

The pipeline follows the LangChain retrieval building blocks: document loader, text splitter, embedding
model and vector store.

## 1. Component architecture

```mermaid
flowchart TB
    subgraph CONFIG[".env settings"]
        direction LR
        C1["OPENAI_EMBEDDING_MODEL"]
        C2["HR_CHUNK_SIZE / HR_CHUNK_OVERLAP<br/>PRODUCT_CHUNK_SIZE / PRODUCT_CHUNK_OVERLAP"]
        C3["INGEST_BATCH_SIZE<br/>EMBEDDING_BATCH_SIZE"]
        C4["STRIP_HEADERS_FOOTERS<br/>VECTORSTORE_DIR, collection names"]
    end

    subgraph SOURCE["Source corpus: data/corpus"]
        HRPDF[["hr_policies/*.pdf<br/>HR and compliance documents"]]
        PMPDF[["product_manuals/**/*.pdf<br/>TV and phone manuals"]]
        MANIFEST[("manifest.json<br/>business metadata per document")]
    end

    INGEST{{"scripts/ingest_vector_stores.py<br/>--store all / hr / products, --reset"}}

    subgraph PIPELINE["data_ingestion.pipeline: one worker per document, INGEST_BATCH_SIZE documents in parallel"]
        direction TB
        LOAD["loading.py<br/>pypdf: one LangChain Document per page<br/>+ common PDF metadata + outline headings"]
        CLEAN["cleaning.py<br/>normalize bullets and control characters<br/>strip repeated headers and footers"]
        SPLIT["chunking.py<br/>RecursiveCharacterTextSplitter<br/>page-level split, add_start_index"]
        META["metadata.py + structure.py<br/>manifest fields, chunk lineage,<br/>section_title, content_type, sanitize"]
        FP{"Fingerprint matches<br/>the stored chunks?"}
        EMBED["embeddings.py<br/>OpenAIEmbeddings<br/>EMBEDDING_BATCH_SIZE texts per request"]
        LOAD --> CLEAN --> SPLIT --> META --> FP
        FP -- "no: new or changed" --> EMBED
    end

    SKIP["Skip: keep existing vectors<br/>(no API call)"]
    OPENAI(["OpenAI Embeddings API<br/>text-embedding-3-small, 1536 dimensions"])

    subgraph WRITE["vectorstore.py: write per document"]
        direction TB
        DEL["delete old chunks of the document"]
        UPS["upsert chunks + vectors + metadata<br/>in EMBEDDING_BATCH_SIZE batches"]
        CMETA["write collection metadata<br/>model, chunk settings, ingested_at"]
        DEL --> UPS --> CMETA
    end

    subgraph STORES["Persistent Chroma databases: data/vectorstores"]
        HRDB[("hr_policies<br/>cosine distance")]
        PMDB[("product_manuals<br/>cosine distance")]
    end

    VALIDATE{{"scripts/validate_vector_stores.py"}}
    REPORT["Summary and config, statistics,<br/>sample records, manifest cross-check,<br/>sample similarity queries"]

    CONFIG -.-> INGEST
    CONFIG -.-> VALIDATE
    HRPDF -- "store: hr" --> INGEST
    PMPDF -- "store: products" --> INGEST
    INGEST --> LOAD
    MANIFEST --> META
    FP -- "yes" --> SKIP
    EMBED <--> OPENAI
    EMBED --> DEL
    CMETA -- "hr store" --> HRDB
    CMETA -- "products store" --> PMDB
    HRDB --> VALIDATE
    PMDB --> VALIDATE
    MANIFEST --> VALIDATE
    VALIDATE -. "sample query embeddings" .-> OPENAI
    VALIDATE --> REPORT
```

## 2. One document's journey (and why re-runs are cheap)

```mermaid
sequenceDiagram
    autonumber
    participant S as ingest_vector_stores.py
    participant P as pipeline.ingest_store
    participant W as Worker thread
    participant O as OpenAI Embeddings API
    participant C as Chroma store

    S->>P: ingest_store(store config, settings, embeddings, manifest)
    P->>C: read collection metadata
    alt --reset, or the embedding model changed
        P->>C: reset_collection()
    end
    P->>C: existing fingerprints {doc_id: {chunk_id: content_hash}}
    loop batches of INGEST_BATCH_SIZE PDFs
        par each PDF in the batch
            P->>W: prepare_document(pdf)
            W->>W: load pages, clean, split, build metadata
            alt fingerprint unchanged
                W-->>P: chunks, no vectors (skip)
            else new or changed
                W->>O: embed_documents(chunks), EMBEDDING_BATCH_SIZE per request
                O-->>W: 1536-dimension vectors
                W-->>P: chunks + vectors
            end
        end
        P->>C: delete(where doc_id) then upsert in batches
    end
    P->>C: delete documents no longer on disk
    P->>C: write collection metadata
    P-->>S: StoreReport (added / updated / unchanged, timings)
```

## 3. How a chunk's metadata is assembled

```mermaid
flowchart LR
    PDF["PDF file"] --> COMMON["Common PDF metadata<br/>source, file_name, file_size_bytes,<br/>page, page_number, total_pages,<br/>pdf_title, pdf_author, pdf_subject,<br/>pdf_keywords, pdf_creator"]
    MAN[("manifest.json")] --> BUSINESS["Corpus manifest fields<br/>doc_id, category, subcategory, title,<br/>publisher, brand, model, model_number,<br/>family, version, status, effective_date,<br/>supersedes, superseded_by"]
    SPLITTER["Text splitter"] --> LINEAGE["Chunk lineage<br/>chunk_id, chunk_index, chunk_index_in_doc,<br/>chunks_in_doc, start_index, char_count,<br/>token_count, content_hash"]
    OUTLINE["PDF outline + line shapes"] --> STRUCT["Structure hints<br/>section_title, content_type"]
    COMMON --> SAN["sanitize_for_chroma<br/>drop None, flatten lists"]
    BUSINESS --> SAN
    LINEAGE --> SAN
    STRUCT --> SAN
    SAN --> RECORD[("Chroma record<br/>id + text + vector + metadata")]
```

## Component responsibilities

| Component | File | Responsibility |
|---|---|---|
| Configuration | `src/data_ingestion/config.py` | Reads `.env`, defines the `hr` and `products` stores |
| Loader | `src/data_ingestion/loading.py` | One `Document` per page, common PDF metadata, outline headings |
| Cleaning | `src/data_ingestion/cleaning.py` | Repairs extraction artefacts; strips repeated headers and footers |
| Structure | `src/data_ingestion/structure.py` | `section_title` from the outline, `content_type` heuristic |
| Splitter | `src/data_ingestion/chunking.py` | `RecursiveCharacterTextSplitter`, page-level, `add_start_index` |
| Metadata | `src/data_ingestion/metadata.py` | Manifest lookup, chunk lineage, deterministic IDs, Chroma-safe values |
| Embeddings | `src/data_ingestion/embeddings.py` | `OpenAIEmbeddings` with `EMBEDDING_BATCH_SIZE` per request |
| Vector store | `src/data_ingestion/vectorstore.py` | Opens, resets and writes the persistent Chroma collections |
| Pipeline | `src/data_ingestion/pipeline.py` | Parallel prepare-and-embed, change detection, per-document replace |
| Validation | `src/data_ingestion/validation.py` | Read-only summaries, cross-checks and sample queries |
| Orchestrators | `scripts/ingest_vector_stores.py`, `scripts/validate_vector_stores.py` | CLI entry points that only coordinate and print |
