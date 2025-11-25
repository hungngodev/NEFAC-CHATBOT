## NEFAC Ingestion Pipeline Overview

### 1. Source Discovery & Metadata
- Crawled documents live under `src/service/crawler/nefac_documents/` with matching metadata JSON files per type (`metadata/<file_type>_metadata.json`).
- `processing.py` is the CLI entry point. It loads the metadata rows, applies filters (`--limit`, `--offset`, `--retry-failures`), enriches each row via `_get_base_metadata`, and dispatches every document to `run_ingestion_workflow`.

### 2. Document Loading (`loader/unstructured_loader.py`)
- `load_document_nodes` is the single loader used by the workflow:
  - Spreadsheets (`.xlsx/.xls/.csv`) are converted with `process_xlsx_intelligently`, keeping sheet names, headers, and structured row metadata.
  - YouTube transcripts (timestamped `.txt` files) are normalised with `parse_timestamps`, preserving start/end times for every chunk.
  - Other formats (PDF, HTML, DOCX, PPTX, plain text) fall back to `unstructured.partition.auto`—there is no LlamaParse dependency.
- Each chunk becomes a `TextNode` with the enriched metadata; the loader also logs per-file progress through `progress_tracker`.

### 3. Workflow Orchestration (`llamaindex/ingestion_workflow.py`)
- The LlamaIndex `Workflow` stages are:
  1. `load_documents` → calls `load_document_nodes` and stores the resulting nodes in workflow context.
  2. `parse_nodes` → pass-through (nodes are already chunked by the loader).
  3. `validate_nodes` → optional empty-chunk filtering when `WORKFLOW_ENABLE_VALIDATION` is true.
  4. `index_qdrant`, `index_elasticsearch`, `index_neo4j` → sequentially push nodes into the configured stores using the helpers in `llamaindex/indexer.py`.
  5. `finalize` → emits the result payload (`success`, `nodes_count`, etc.).
- The workflow exposes `run_ingestion_workflow` and a convenience `SimpleIngestionPipeline` wrapper for programmatic use outside the CLI.

### 4. Indexing & Storage Integration
- `llamaindex/indexer.py` centralises Qdrant, Elasticsearch, and Neo4j integrations. It honours the environment toggles (`QDRANT_ENABLE`, `ES_LI_ENABLE`, `GRAPH_LI_ENABLE`, `GRAPH_MODE`) and passes the dedicated graph LLM into `LegalPropertyGraphIngestor`.
- `llamaindex/property_graph_ingestor.py` and `llamaindex/entity_deduplication.py` implement schema-aware Neo4j ingestion, stats, deduplication, and maintenance helpers.
- `llamaindex/database_cleaner.py` provides a CLI-invoked reset for the three backing stores.

### 5. Operational Support
- `progress_tracker.py` records detailed per-file logs, aggregates stats, and persists failure metadata to `ingestion_failures.json` so runs can be retried with `--retry-failures`.
- `llamaindex/diagnostics.py` checks that required Python packages and environment variables are set before ingestion proceeds.
- CLI options exposed by `processing.py` include file-type selection, batching controls, failure replay, and a `--clear` flag to invoke the database cleaner beforehand.

### 6. Configuration (`settings.py`)
- Loads `.env` values (OpenAI keys, model names, indexing toggles) and wires them into LlamaIndex `Settings`.
- Surfaces tuning knobs for hybrid retrieval weights, workflow retry behaviour, and Neo4j/entity-deduplication thresholds.

Run `python -m src.service.ingestion_service.processing --help` to view all supported CLI flags and options.
