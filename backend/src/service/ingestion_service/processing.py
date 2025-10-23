"""NEFAC Document Ingestion Pipeline - Clean, Systematic Processing.

Augmented with durable retry support inspired by the Elastic + LlamaIndex
workflow reference so failed files can be replayed safely.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import argparse
import asyncio
import json
import logging
import os
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

from dotenv import load_dotenv
from llama_index.core.schema import BaseNode

from src.service.ingestion_service.llamaindex import ensure_llamaindex_ready
from src.service.ingestion_service.llamaindex.database_cleaner import clear_all_databases
from src.service.ingestion_service.loader.unstructured_loader import (
    _get_base_metadata,
    unstructured_loader,
)
from src.service.ingestion_service.progress_tracker import (
    FailureRecord,
    PipelineTracker,
    get_tracker,
    reset_tracker,
)
from src.service.ingestion_service.settings import (
    ENABLE_CONTEXTUAL_RETRIEVAL,
    ENABLE_METADATA_EXTRACTION,
    GRAPH_LLM_MODEL_NAME,
    GRAPH_MODE,
    LLAMAPARSE_ENABLE,
    LLM_MODEL_NAME,
    USE_LLAMAINDEX_WORKFLOW,
    embedding_model,
)

load_dotenv()

# Centralized logging (configured lazily so imports do not create files)
logger = logging.getLogger(__name__)
_LOGGING_CONFIGURED = False
_STARTUP_READY = False


def _configure_logging() -> None:
    """Configure logging once per process."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_file = f"ingestion_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(stream_handler)

    root_logger.addHandler(file_handler)
    _LOGGING_CONFIGURED = True


def _ensure_startup_ready() -> None:
    global _STARTUP_READY
    if _STARTUP_READY:
        return

    if not _LOGGING_CONFIGURED:
        _configure_logging()

    try:
        ensure_llamaindex_ready()
        _STARTUP_READY = True
    except Exception as exc:
        logger.error("Startup diagnostics failed: %s", exc)
        raise


# Supported file types (all handled by unified loader)
SUPPORTED_FILE_TYPES = ["pdf", "html", "youtube", "xlsx"]
_TRUTHY = {"1", "true", "yes", "on"}

FAILURES_FILENAME = "ingestion_failures.json"
DEFAULT_FAILURE_LOG = Path(__file__).parent / FAILURES_FILENAME

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
    include_only: Optional[Set[str]] = None,
) -> List[dict]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    if offset:
        raw_entries = raw_entries[offset:]

    window = raw_entries[:limit] if limit else raw_entries
    entries = [entry for entry in window if entry.get("filename")]

    if include_only:
        entries = [entry for entry in entries if entry.get("filename") in include_only]

    return entries


def _resolve_file_path(documents_dir: str, filename: str) -> Path:
    path = Path(documents_dir) / filename if not os.path.isabs(filename) else Path(filename)
    return path


def _group_failures_by_type(failures: Iterable[FailureRecord]) -> Dict[str, Set[str]]:
    grouped: Dict[str, Set[str]] = defaultdict(set)
    for record in failures:
        grouped[record.file_type].add(record.filename)
    return grouped


def _ingest_with_workflow(
    file_type: str,
    metadata_json_path: str,
    documents_dir: str,
    limit: Optional[int],
    offset: int,
    include_only: Optional[Set[str]] = None,
) -> None:
    from src.service.ingestion_service.llamaindex.ingestion_workflow import run_ingestion_workflow

    _configure_logging()
    tracker = get_tracker()
    entries = _load_metadata_entries(metadata_json_path, limit, offset, include_only)

    if not entries:
        logger.warning(f"No documents found for {file_type} via workflow. Skipping.")
        return

    contextual_enabled = ENABLE_CONTEXTUAL_RETRIEVAL
    metadata_enabled = ENABLE_METADATA_EXTRACTION
    es_enabled = os.getenv("ES_LI_ENABLE", "true").lower() in _TRUTHY
    graph_enabled = os.getenv("GRAPH_LI_ENABLE", "true").lower() in _TRUTHY
    llamaparse_enabled = LLAMAPARSE_ENABLE

    total_nodes = 0

    for index, entry in enumerate(entries, 1):
        filename = entry["filename"]
        tracker.log_file_start(file_type, filename, index, len(entries))

        path = _resolve_file_path(documents_dir, filename)
        if not path.exists():
            logger.warning(f"  │   └── ❌ File not found: {filename}")
            tracker.record_failure(file_type, filename, "missing_file", "file not found")
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
                    return_nodes=False,
                )
            )

            if not result.get("success", True):
                raise RuntimeError(result.get("error") or "workflow reported failure")

            nodes_count = int(result.get("nodes_count", 0))
            total_nodes += nodes_count

            tracker.log_file_phase("Workflow ingestion", count=nodes_count)
            tracker.log_file_complete(filename, nodes_count, 0)
            tracker.mark_success(file_type, filename)

        except Exception as exc:
            logger.error(f"Workflow ingestion failed for {filename}: {exc}")
            tracker.record_failure(file_type, filename, "workflow", exc)
            continue

    logger.info(f"  └── ✅ Workflow processed {total_nodes} chunks for {file_type.upper()} files")

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
        if GRAPH_MODE == "off":
            logger.info("Graph mode 'off' - skipping graph ingestion")
            return

        if os.getenv("GRAPH_LI_ENABLE", "true").lower() in _TRUTHY:
            from src.service.ingestion_service.llamaindex.indexer import index_nodes_to_neo4j

            use_property_graph = GRAPH_MODE in {"property", "legal", "schema"}
            ingested_count = index_nodes_to_neo4j(nodes, use_property_graph=use_property_graph)
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
            index_nodes_to_elasticsearch,
            index_nodes_to_qdrant,
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
    include_only: Optional[Set[str]] = None,
) -> None:
    _ensure_startup_ready()
    _configure_logging()
    tracker = get_tracker()
    tracker.log_phase_start(f"Processing {file_type.upper()} files")

    try:
        env_workflow = USE_LLAMAINDEX_WORKFLOW
        effective_use_workflow = use_workflow or env_workflow

        metadata_path = get_metadata_path(file_type)
        documents_dir = str(DOCS_BASE_DIR / file_type)

        if include_only and not effective_use_workflow:
            logger.warning(
                "Retry targets supplied for %s but workflow mode is disabled; " "falling back to legacy loader for matching files only.",
                file_type,
            )

        if effective_use_workflow:
            _ingest_with_workflow(
                file_type,
                metadata_path,
                documents_dir,
                limit,
                offset,
                include_only,
            )
            return

        processed_filenames: Optional[Set[str]] = set() if include_only else None
        nodes = unstructured_loader(
            metadata_path,
            documents_dir,
            limit,
            offset,
            file_type=file_type,
            include_only=include_only,
            processed_filenames=processed_filenames,
        )

        if not nodes:
            logger.warning(f"No documents found for {file_type}. Skipping.")
            return

        contextual_indexing(nodes, file_type)
        graph_rag_ingest(nodes, file_type)

        if include_only and processed_filenames is not None:
            for filename in processed_filenames:
                tracker.mark_success(file_type, filename)

            missing = include_only - processed_filenames
            for filename in missing:
                logger.warning("Retry target %s was not processed", filename)

    except Exception as e:
        logger.error(f"Failed processing {file_type}: {e}")
        traceback.print_exc()
        tracker.record_failure(file_type, "__batch__", "pipeline", e)
    finally:
        tracker.log_phase_end(f"Processing {file_type.upper()} files")


def process_all_file_types(
    limit: Optional[int] = None,
    offset: int = 0,
    clear_databases: bool = False,
    use_workflow: bool = False,
    failures_file: Path = DEFAULT_FAILURE_LOG,
    retry_failures: bool = False,
) -> None:
    _ensure_startup_ready()
    _configure_logging()
    reset_tracker()
    tracker = get_tracker()
    tracker.log_phase_start("NEFAC Document Ingestion Pipeline")

    failure_targets: Dict[str, Set[str]] = {}
    if retry_failures:
        seeded_failures = PipelineTracker.load_failures(failures_file)
        failure_targets = _group_failures_by_type(seeded_failures)
        tracker.seed_failures(seeded_failures)

    if clear_databases:
        logger.info("🧹 Clearing existing database data...")
        clear_results = clear_all_databases()
        failed_dbs = [db for db, success in clear_results.items() if not success]
        if failed_dbs:
            logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        else:
            logger.info("All databases cleared successfully.")

    for file_type in SUPPORTED_FILE_TYPES:
        include_only = failure_targets.get(file_type) if retry_failures else None
        if retry_failures and not include_only:
            continue
        process_file_type(
            file_type,
            limit,
            offset,
            use_workflow=use_workflow,
            include_only=include_only,
        )

    tracker.log_phase_end("NEFAC Document Ingestion Pipeline")
    tracker.log_summary()
    tracker.export_failures(failures_file)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument("--file-type", choices=SUPPORTED_FILE_TYPES + ["all"], default="all", help="Type of documents to process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first X documents")
    parser.add_argument("--clear", action="store_true", help="Clear existing database data before processing")
    parser.add_argument("--workflow", action="store_true", help="Run ingestion via LlamaIndex Workflow")
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Replay documents that failed in the previous run (workflow mode recommended)",
    )
    parser.add_argument(
        "--failures-file",
        type=Path,
        default=DEFAULT_FAILURE_LOG,
        help="Path to the failure log JSON (stores workflow replay metadata)",
    )
    args = parser.parse_args()

    if args.file_type == "all":
        process_all_file_types(
            limit=args.limit,
            offset=args.offset,
            clear_databases=args.clear,
            use_workflow=args.workflow,
            failures_file=args.failures_file,
            retry_failures=args.retry_failures,
        )
    else:
        reset_tracker()
        tracker = get_tracker()
        if args.clear:
            logger.info("🧹 Clearing existing database data...")
            clear_all_databases()

        include_only: Optional[Set[str]] = None
        if args.retry_failures:
            seeded_failures = PipelineTracker.load_failures(args.failures_file)
            tracker.seed_failures(seeded_failures)
            include_map = _group_failures_by_type(seeded_failures)
            include_only = include_map.get(args.file_type)
            if not include_only:
                logger.info("No recorded failures for %s", args.file_type)

        process_file_type(
            args.file_type,
            args.limit,
            args.offset,
            use_workflow=args.workflow,
            include_only=include_only,
        )

        tracker.log_summary()
        tracker.export_failures(args.failures_file)


if __name__ == "__main__":
    main()
