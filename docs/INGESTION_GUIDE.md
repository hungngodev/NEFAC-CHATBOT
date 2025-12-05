# NEFAC Ingestion Documentation

## 1. Overview

The NEFAC Ingestion Service is a robust, event-driven pipeline built on **LlamaIndex Workflows**. It implements a **Hybrid RAG** architecture, simultaneously populating Vector Stores (Qdrant), Search Engines (Elasticsearch), and Knowledge Graphs (Neo4j) to enable multifaceted retrieval strategies.

- **Architecture**: Event-Driven Workflow (LlamaIndex).
- **Storage Strategy**: Hybrid (Vector + Keyword + Graph).
- **Orchestration**: Asyncio + Custom Pipeline Tracker.
- **Entry Point**: `src/service/ingestion_service/processing.py`.

## 2. Data Flow

### 2.1 Pipeline Execution (`processing.py`)

1.  **Initialization**: Loads metadata from `nefac_documents/metadata/*.json`.
2.  **Filtering**: Applies limits, offsets, or failure-replay filters.
3.  **Workflow Trigger**: For each file, launches `run_ingestion_workflow`.

### 2.2 Ingestion Workflow (`ingestion_workflow.py`)

The workflow executes as a directed acyclic graph (DAG) of events:

1.  **`load_documents`**:
    - Checks `cache/nodes/` for existing parsed nodes (MD5 hash).
    - If miss, calls `unstructured_loader` to parse PDF/HTML/YouTube.
    - Emits: `NodesCreatedEvent`.
2.  **`parse_nodes`**:
    - (Placeholder for advanced chunking). Emits: `ParsedNodesEvent`.
3.  **`validate_nodes`**:
    - Filters out empty or malformed nodes. Emits: `ValidatedNodesEvent`.
4.  **`index_all`**:
    - **Parallel Execution**: Uploads to enabled stores concurrently.
    - **Qdrant**: Dense vector embeddings.
    - **Elasticsearch**: Sparse keyword indices.
    - **Neo4j**: Property graph extraction (Entities + Relationships).
    - Emits: `IndexedEvent`.

### 2.3 Advanced Features

- **Transcript Parsing**: Automatically detects timestamp patterns (e.g., `[10:30]`) in `.txt` files, adding `start_time`/`end_time` metadata for playback sync.
- **Spreadsheet Intelligence**: Preserves tabular structure in `.xlsx`/`.csv` files, converting rows to context-rich text strings rather than raw dumps.

## 3. Configuration & Arguments

### 3.1 Command Line Interface

| Argument           | Flag                    | Default | Description                                             |
| :----------------- | :---------------------- | :------ | :------------------------------------------------------ |
| **Selection**      | `--file-type`           | `all`   | Types to process (`pdf`, `html`, `youtube`, `xlsx`).    |
|                    | `--limit`               | `None`  | Max documents to process.                               |
|                    | `--offset`              | `0`     | Skip the first X documents.                             |
|                    | `--retry-failures`      | `False` | Replay only failed docs from `ingestion_failures.json`. |
| **Modes**          | `--graph-rag-only`      | `False` | Run ONLY Graph RAG (disable Vector/Keyword).            |
|                    | `--es-only`             | `False` | Run ONLY Elasticsearch.                                 |
|                    | `--qdrant-only`         | `False` | Run ONLY Qdrant.                                        |
|                    | `--skip-graph`          | `False` | Skip Graph RAG.                                         |
|                    | `--skip-es`             | `False` | Skip Elasticsearch.                                     |
|                    | `--skip-qdrant`         | `False` | Skip Qdrant.                                            |
|                    | `--clear`               | `False` | Wipe databases before starting.                         |
| **Graph Features** | `--community-detection` | `False` | Run Leiden algorithm on Neo4j.                          |
|                    | `--topic-extraction`    | `False` | Enable LLM-based topic extraction.                      |
|                    | `--citation-linking`    | `False` | Enable legal citation linking.                          |
|                    | `--temporal-linking`    | `False` | Enable temporal linking (NEXT_IN_TIME).                 |
|                    | `--entity-cooccurrence` | `False` | Enable entity co-occurrence linking.                    |
|                    | `--no-semantic-linking` | `False` | Disable semantic linking.                               |
| **Misc**           | `--invalidCache`        | `False` | Invalidate cache for processed files.                   |

### 3.2 Settings (`settings.py`)

- **Chunking**: `CHUNK_SIZE=384`, `CHUNK_OVERLAP=38`.
- **Graph Schema**:
  - `ALLOWED_NODES`: `Person`, `Organization`, `LegalCase`, etc.
  - `ENTITY_ALIASES`: Maps `ACLU of MA` -> `ACLU`.
- **Deduplication**: `GRAPH_ENABLE_ENTITY_DEDUPLICATION=True` (Threshold: 0.9).

## 4. Embedding & Vectorization

### 4.1 Models

- **Embeddings**: `openai:text-embedding-3-small` (via `OpenAIEmbedding`).
- **Graph Extraction**: `openai:gpt-5-nano` (Service Tier: `flex`).
  - Used by `DynamicLLMPathExtractor` to identify entities and relationships.

### 4.2 Storage

- **Qdrant**: Stores dense vectors for semantic search.
- **Elasticsearch**: Stores text for BM25 keyword search.
- **Neo4j**: Stores the Knowledge Graph (Nodes + Edges).

### 4.3 Property Graph Schema & Deduplication (`settings.py`)

The system enforces a strict legal ontology to maintain graph quality.

- **Allowed Nodes**: `Person`, `Organization`, `LegalCase`, `LawOrPolicy`, `Statute`, `Court`, `Judge`, etc.
- **Allowed Relationships**: `WORKS_FOR`, `CITES`, `CHALLENGES`, `ENFORCES`, `DECIDED_BY`, etc.
- **Entity Deduplication**:
  1.  **Pre-Ingestion**: Regex-based alias replacement (e.g., "ACLU of MA" -> "ACLU").
  2.  **Post-Ingestion**: `EntityDeduplicator` merges nodes based on:
      - **Vector Similarity**: > 0.9 (using `text-embedding-3-small`).
      - **Edit Distance**: < 2 characters.

## 5. Orchestration & Scaling

### 5.1 Concurrency

- **Asyncio**: The pipeline runs in a single process but uses `asyncio` for I/O-bound tasks (DB writes, API calls).
- **Graph Workers**: `GRAPH_NUM_WORKERS=1` (Controlled in `settings.py` to avoid rate limits).

### 5.2 Fault Tolerance (`PipelineTracker`)

- **State Tracking**: Records success/failure per file in `ingestion_failures.json`.
- **Resume Capability**: `--retry-failures` reads the log to re-process only dropped items.
- **Rate Limiting**: Exponential backoff for OpenAI/Neo4j errors.

## 6. Dependencies & Setup

### 6.1 Key Libraries

- `llama-index`: Core RAG framework.
- `unstructured`: Document parsing.
- `spacy`: NLP tasks (Semantic Splitter).
- `networkx` / `cdlib`: Community detection.

### 6.2 Development Setup

**Location**: `backend/`
**Entry Point**: `src.service.ingestion_service.processing`

1.  **Install Dependencies**:
    ```bash
    cd backend
    poetry install
    ```

2.  **Run Ingestion**:
    Execute the module via Poetry:

    **Full Ingestion (All Types)**:
    ```bash
    poetry run python -m src.service.ingestion_service.processing --file-type all
    ```

    **Specific Type (e.g., PDF)**:
    ```bash
    poetry run python -m src.service.ingestion_service.processing --file-type pdf
    ```

    **Clear & Restart**:
    ```bash
    poetry run python -m src.service.ingestion_service.processing --clear --file-type all
    ```
