"""
NEFAC Document Ingestion Pipeline - Clean, Systematic Processing
Supports PDF, HTML, YouTube transcripts, and XLSX with intelligent processing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import argparse
import asyncio
import logging
import os
import json
import traceback
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from llama_index.core.schema import BaseNode

from src.service.ingestion_service.llamaindex.database_cleaner import clear_all_databases
from src.service.ingestion_service.loader.unstructured_loader import (
    unstructured_loader,
    _get_base_metadata,
)
from src.service.ingestion_service.progress_tracker import get_tracker, reset_tracker
from src.service.ingestion_service.settings import (
    GRAPH_LLM_MODEL_NAME,
    LLM_MODEL_NAME,
    embedding_model,
)

load_dotenv()

# Setup centralized logging
log_file = f"ingestion_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(message)s", datefmt="%H:%M:%S", handlers=[logging.FileHandler(log_file), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Supported file types (all handled by unified loader)
SUPPORTED_FILE_TYPES = ["pdf", "html", "youtube", "xlsx"]
_TRUTHY = {"1", "true", "yes", "on"}

# Resolve important directories relative to the backend folder for portability
BACKEND_DIR = Path(__file__).parents[3]
DOCS_BASE_DIR = BACKEND_DIR / "src/service/crawler/nefac_documents"


def get_metadata_path(file_type: str) -> str:
    """Return the metadata JSON path for the given file type."""
    return str(DOCS_BASE_DIR / "metadata" / f"{file_type}_metadata.json")


def _load_metadata_entries(
    metadata_json_path: str,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[dict]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    if offset:
        raw_entries = raw_entries[offset:]

    window = raw_entries[:limit] if limit else raw_entries
    return [entry for entry in window if entry.get("filename")]


def _resolve_file_path(documents_dir: str, filename: str) -> Path:
    path = Path(documents_dir) / filename if not os.path.isabs(filename) else Path(filename)
    return path


def _ingest_with_workflow(
    file_type: str,
    metadata_json_path: str,
    documents_dir: str,
    limit: Optional[int],
    offset: int,
) -> None:
    from src.service.ingestion_service.llamaindex.ingestion_workflow import run_ingestion_workflow

    tracker = get_tracker()
    entries = _load_metadata_entries(metadata_json_path, limit, offset)

    if not entries:
        logger.warning(f"No documents found for {file_type} via workflow. Skipping.")
        return

    contextual_enabled = os.getenv("ENABLE_CONTEXTUAL_RETRIEVAL", "true").lower() in _TRUTHY
    metadata_enabled = os.getenv("ENABLE_METADATA_EXTRACTION", "false").lower() in _TRUTHY
    es_enabled = os.getenv("ES_LI_ENABLE", "true").lower() in _TRUTHY
    graph_enabled = os.getenv("GRAPH_LI_ENABLE", "true").lower() in _TRUTHY
    llamaparse_enabled = os.getenv("LLAMAPARSE_ENABLE", "false").lower() in _TRUTHY

    total_nodes = 0

    for index, entry in enumerate(entries, 1):
        filename = entry["filename"]
        tracker.log_file_start(file_type, filename, index, len(entries))

        path = _resolve_file_path(documents_dir, filename)
        if not path.exists():
            logger.warning(f"  │   └── ❌ File not found: {filename}")
            continue

        base_meta = _get_base_metadata(str(path), entry)
        document_meta = base_meta.copy()
        document_meta.update({k: v for k, v in (entry or {}).items() if v is not None})

        try:
            result = asyncio.run(
                run_ingestion_workflow(
                    str(path),
                    metadata=document_meta,
                    enable_qdrant=True,
                    enable_elasticsearch=es_enabled,
                    enable_neo4j=graph_enabled,
                    enable_contextual_retrieval=contextual_enabled,
                    enable_metadata_extraction=metadata_enabled,
                    use_llamaparse=llamaparse_enabled,
                )
            )

            nodes_count = int(result.get("nodes_count", 0))
            total_nodes += nodes_count

            tracker.log_file_phase("Workflow ingestion", count=nodes_count)
            tracker.log_file_complete(filename, nodes_count, 0)

        except Exception as exc:
            logger.error(f"Workflow ingestion failed for {filename}: {exc}")
            continue

    logger.info(
        f"  └── ✅ Workflow processed {total_nodes} chunks for {file_type.upper()} files"
    )

    tracker.track_phase_stats(file_type, "chunks_created", total_nodes)
    tracker.track_phase_stats(file_type, "chunks_contextualized", total_nodes)
    tracker.track_phase_stats("global", "chunks_created", total_nodes)
    tracker.track_phase_stats("global", "chunks_contextualized", total_nodes)


def graph_rag_ingest(nodes: List[BaseNode], file_type: str) -> None:
    if not nodes:
        return

    tracker = get_tracker()
    tracker.log_pipeline_step("Graph RAG Ingestion", GRAPH_LLM_MODEL_NAME)

    try:
        if os.getenv("GRAPH_LI_ENABLE", "true").lower() in _TRUTHY:
            from src.service.ingestion_service.llamaindex.indexer import index_nodes_to_neo4j

            ingested_count = index_nodes_to_neo4j(nodes)
            tracker.track_db_upload(file_type, "Neo4j", ingested_count)
        else:
            logger.info("GRAPH_LI_ENABLE disabled - skipping graph ingestion")

    except Exception as e:
        logger.error(f"Graph RAG ingestion failed: {e}")
        raise


def contextual_indexing(nodes: List[BaseNode], file_type: str) -> None:
    if not nodes:
        return

    tracker = get_tracker()
    tracker.log_pipeline_step("Contextual Indexing", getattr(embedding_model, "model_name", LLM_MODEL_NAME))

    try:
        from src.service.ingestion_service.llamaindex.indexer import (
            index_nodes_to_qdrant,
            index_nodes_to_elasticsearch,
        )

        index_nodes_to_qdrant(nodes, embedding_model)
        tracker.track_db_upload(file_type, "Qdrant", len(nodes))

        if os.getenv("ES_LI_ENABLE", "true").lower() in _TRUTHY:
            index_nodes_to_elasticsearch(nodes, embedding_model)
            tracker.track_db_upload(file_type, "Elasticsearch", len(nodes))
        else:
            logger.info("ES_LI_ENABLE disabled - skipping Elasticsearch ingestion")

    except Exception as e:
        logger.error(f"Contextual indexing failed: {e}")
        raise


def process_file_type(
    file_type: str,
    limit: Optional[int] = None,
    offset: int = 0,
    use_workflow: bool = False,
) -> None:
    tracker = get_tracker()
    tracker.log_phase_start(f"Processing {file_type.upper()} files")

    try:
        env_workflow = os.getenv("USE_LLAMAINDEX_WORKFLOW", "false").lower() in _TRUTHY
        effective_use_workflow = use_workflow or env_workflow

        metadata_path = get_metadata_path(file_type)
        documents_dir = str(DOCS_BASE_DIR / file_type)

        if effective_use_workflow:
            _ingest_with_workflow(file_type, metadata_path, documents_dir, limit, offset)
            return

        nodes = unstructured_loader(metadata_path, documents_dir, limit, offset, file_type=file_type)

        if not nodes:
            logger.warning(f"No documents found for {file_type}. Skipping.")
            return

        contextual_indexing(nodes, file_type)
        graph_rag_ingest(nodes, file_type)

    except Exception as e:
        logger.error(f"Failed processing {file_type}: {e}")
        traceback.print_exc()
    finally:
        tracker.log_phase_end(f"Processing {file_type.upper()} files")


def process_all_file_types(
    limit: Optional[int] = None,
    offset: int = 0,
    clear_databases: bool = False,
    use_workflow: bool = False,
) -> None:
    reset_tracker()
    tracker = get_tracker()
    tracker.log_phase_start("NEFAC Document Ingestion Pipeline")

    if clear_databases:
        logger.info("🧹 Clearing existing database data...")
        clear_results = clear_all_databases()
        failed_dbs = [db for db, success in clear_results.items() if not success]
        if failed_dbs:
            logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        else:
            logger.info("All databases cleared successfully.")

    for file_type in SUPPORTED_FILE_TYPES:
        process_file_type(file_type, limit, offset, use_workflow=use_workflow)

    tracker.log_phase_end("NEFAC Document Ingestion Pipeline")
    tracker.log_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument("--file-type", choices=SUPPORTED_FILE_TYPES + ["all"], default="all", help="Type of documents to process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first X documents")
    parser.add_argument("--clear", action="store_true", help="Clear existing database data before processing")
    parser.add_argument("--workflow", action="store_true", help="Run ingestion via LlamaIndex Workflow")
    args = parser.parse_args()

    if args.file_type == "all":
        process_all_file_types(
            limit=args.limit,
            offset=args.offset,
            clear_databases=args.clear,
            use_workflow=args.workflow,
        )
    else:
        reset_tracker()
        tracker = get_tracker()
        if args.clear:
            logger.info("🧹 Clearing existing database data...")
            clear_all_databases()

        process_file_type(
            args.file_type,
            args.limit,
            args.offset,
            use_workflow=args.workflow,
        )

        tracker.log_summary()


if __name__ == "__main__":
    main()
