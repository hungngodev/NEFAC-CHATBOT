from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from load_env import load_env as load_env_from_root
from src.service.ingestion_service.llamaindex.database_cleaner import clear_all_databases
from src.service.ingestion_service.llamaindex.ingestion_workflow import run_ingestion_workflow
from src.service.ingestion_service.llamaindex.metadata_utils import _get_base_metadata
from src.service.ingestion_service.progress_tracker import (
    FailureRecord,
    PipelineTracker,
    get_tracker,
    reset_tracker,
)

load_env_from_root()

logger = logging.getLogger(__name__)
_LOGGING_CONFIGURED = False
_STARTUP_READY = False


def _configure_logging() -> None:
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
        # ensure_llamaindex_ready()
        _STARTUP_READY = True
    except Exception as exc:
        logger.error("Startup diagnostics failed: %s", exc)
        raise


SUPPORTED_FILE_TYPES = ["pdf", "html", "youtube", "xlsx"]
_TRUTHY = {"1", "true", "yes", "on"}

FAILURES_FILENAME = "ingestion_failures.json"
DEFAULT_FAILURE_LOG = Path(__file__).parent / FAILURES_FILENAME

BACKEND_DIR = Path(__file__).parents[3]
DOCS_BASE_DIR = BACKEND_DIR / "src/service/crawler/nefac_documents"


def get_metadata_path(file_type: str) -> str:
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
    return Path(documents_dir) / filename if not os.path.isabs(filename) else Path(filename)


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
    graph_rag_only: bool = False,
    skip_graph: bool = False,
    es_only: bool = False,
    qdrant_only: bool = False,
    skip_es: bool = False,
    skip_qdrant: bool = False,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    invalidate_cache: bool = False,
) -> None:
    _configure_logging()
    tracker = get_tracker()
    entries = _load_metadata_entries(metadata_json_path, limit, offset, include_only)

    if not entries:
        logger.warning(f"No documents found for {file_type} via workflow. Skipping.")
        return

    # Default state: check env vars or default to True
    default_es = os.getenv("ES_LI_ENABLE", "true").lower() in _TRUTHY
    default_qdrant = True
    default_graph = os.getenv("GRAPH_LI_ENABLE", "true").lower() in _TRUTHY

    # Initialize flags
    es_enabled = default_es
    qdrant_enabled = default_qdrant
    graph_enabled = default_graph

    # Apply "ONLY" flags (exclusive)
    if graph_rag_only:
        es_enabled = False
        qdrant_enabled = False
        graph_enabled = True
        logger.info("🚀 Running in GRAPH RAG ONLY mode")
    elif es_only:
        es_enabled = True
        qdrant_enabled = False
        graph_enabled = False
        logger.info("🚀 Running in ELASTICSEARCH ONLY mode")
    elif qdrant_only:
        es_enabled = False
        qdrant_enabled = True
        graph_enabled = False
        logger.info("🚀 Running in QDRANT ONLY mode")
    elif skip_graph:
        graph_enabled = False
        logger.info("🚀 Running in VECTOR STORE ONLY mode (Graph RAG disabled)")

    # Apply "SKIP" flags (subtractive)
    if skip_es:
        es_enabled = False
        logger.info("🚫 Skipping Elasticsearch")
    if skip_qdrant:
        qdrant_enabled = False
        logger.info("🚫 Skipping Qdrant")

    logger.info(f"Configuration: ES={es_enabled}, Qdrant={qdrant_enabled}, Graph={graph_enabled}")

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
        document_meta["file_type"] = file_type

        try:
            logger.info(f"DEBUG: Calling workflow with invalidate_cache={invalidate_cache}")
            result = asyncio.run(
                run_ingestion_workflow(
                    str(path),
                    metadata=document_meta,
                    enable_qdrant=qdrant_enabled,
                    enable_elasticsearch=es_enabled,
                    enable_neo4j=graph_enabled,
                    return_nodes=False,
                    run_semantic_linking=run_semantic_linking,
                    run_community_detection=run_community_detection,
                    run_topic_extraction=run_topic_extraction,
                    run_citation_linking=run_citation_linking,
                    run_temporal_linking=run_temporal_linking,
                    run_entity_cooccurrence=run_entity_cooccurrence,
                    invalidate_cache=invalidate_cache,
                )
            )

            if not result.get("success", True):
                raise RuntimeError(result.get("error") or "workflow reported failure")

            nodes_count = int(result.get("nodes_count", 0))
            total_nodes += nodes_count

            tracker.log_file_phase("Workflow ingestion", count=nodes_count)
            tracker.log_file_complete(filename, nodes_count, 0)

            if nodes_count == 0:
                tracker.track_phase_stats(file_type, "files_skipped", 1)

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


def process_file_type(
    file_type: str,
    limit: Optional[int] = None,
    offset: int = 0,
    include_only: Optional[Set[str]] = None,
    graph_rag_only: bool = False,
    skip_graph: bool = False,
    es_only: bool = False,
    qdrant_only: bool = False,
    skip_es: bool = False,
    skip_qdrant: bool = False,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    invalidate_cache: bool = False,
) -> None:
    _ensure_startup_ready()
    _configure_logging()
    tracker = get_tracker()
    tracker.log_phase_start(f"Processing {file_type.upper()} files")

    try:
        metadata_path = get_metadata_path(file_type)
        documents_dir = str(DOCS_BASE_DIR / file_type)

        _ingest_with_workflow(
            file_type,
            metadata_path,
            documents_dir,
            limit,
            offset,
            include_only,
            graph_rag_only=graph_rag_only,
            skip_graph=skip_graph,
            es_only=es_only,
            qdrant_only=qdrant_only,
            skip_es=skip_es,
            skip_qdrant=skip_qdrant,
            run_semantic_linking=run_semantic_linking,
            run_community_detection=run_community_detection,
            run_topic_extraction=run_topic_extraction,
            run_citation_linking=run_citation_linking,
            run_temporal_linking=run_temporal_linking,
            run_entity_cooccurrence=run_entity_cooccurrence,
            invalidate_cache=invalidate_cache,
        )

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
    failures_file: Path = DEFAULT_FAILURE_LOG,
    retry_failures: bool = False,
    graph_rag_only: bool = False,
    skip_graph: bool = False,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    invalidate_cache: bool = False,
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
            include_only=include_only,
            graph_rag_only=graph_rag_only,
            skip_graph=skip_graph,
            run_semantic_linking=run_semantic_linking,
            run_community_detection=run_community_detection,
            run_topic_extraction=run_topic_extraction,
            run_citation_linking=run_citation_linking,
            run_temporal_linking=run_temporal_linking,
            run_entity_cooccurrence=run_entity_cooccurrence,
            invalidate_cache=invalidate_cache,
        )

    tracker.log_phase_end("NEFAC Document Ingestion Pipeline")
    tracker.log_summary()
    tracker.export_failures(failures_file)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument(
        "--file-type",
        nargs="+",
        choices=SUPPORTED_FILE_TYPES + ["all"],
        default=["all"],
        help="Type of documents to process (can specify multiple)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first X documents")
    parser.add_argument("--clear", action="store_true", help="Clear existing database data before processing")
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
    parser.add_argument(
        "--graph-rag-only",
        action="store_true",
        help="Only perform Graph RAG ingestion (disable vector stores)",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip Graph RAG ingestion (Qdrant + Elasticsearch only)",
    )
    parser.add_argument(
        "--es-only",
        action="store_true",
        help="Only perform Elasticsearch ingestion",
    )
    parser.add_argument(
        "--qdrant-only",
        action="store_true",
        help="Only perform Qdrant ingestion",
    )
    parser.add_argument(
        "--skip-es",
        action="store_true",
        help="Skip Elasticsearch ingestion",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant ingestion",
    )
    parser.add_argument(
        "--no-semantic-linking",
        action="store_true",
        help="Disable semantic linking (enabled by default)",
    )
    parser.add_argument(
        "--community-detection",
        action="store_true",
        help="Enable community detection (Leiden algorithm)",
    )
    parser.add_argument(
        "--topic-extraction",
        action="store_true",
        help="Enable LLM-based topic extraction",
    )
    parser.add_argument(
        "--citation-linking",
        action="store_true",
        help="Enable legal citation linking",
    )
    parser.add_argument(
        "--temporal-linking",
        action="store_true",
        help="Enable temporal linking (NEXT_IN_TIME)",
    )
    parser.add_argument(
        "--entity-cooccurrence",
        action="store_true",
        help="Enable entity co-occurrence linking (RELATED_TO)",
    )
    parser.add_argument(
        "--invalidCache",
        action="store_true",
        help="Invalidate cache for processed files only",
    )
    args = parser.parse_args()

    if args.graph_rag_only and args.skip_graph:
        parser.error("Cannot use both --graph-rag-only and --skip-graph at the same time")

    # Normalize file_types input
    file_types = args.file_type
    if "all" in file_types:
        file_types = SUPPORTED_FILE_TYPES

    reset_tracker()
    tracker = get_tracker()
    tracker.log_phase_start("NEFAC Document Ingestion Pipeline")

    # 1. Clear databases ONCE if requested
    if args.clear:
        logger.info("🧹 Clearing existing database data...")

        # Determine what to clear based on flags
        # Default: clear everything unless specific flags are set
        clear_es = True
        clear_qdrant = True
        clear_graph = True

        # If "only" flags are used, restrict clearing
        if args.es_only:
            clear_es = True
            clear_qdrant = False
            clear_graph = False
        elif args.qdrant_only:
            clear_es = False
            clear_qdrant = True
            clear_graph = False
        elif args.graph_rag_only:
            clear_es = False
            clear_qdrant = False
            clear_graph = True

        # If "skip" flags are used, disable specific clearing
        if args.skip_es:
            clear_es = False
        if args.skip_qdrant:
            clear_qdrant = False
        if args.skip_graph:
            clear_graph = False

        clear_results = clear_all_databases(
            clear_qdrant=clear_qdrant,
            clear_elasticsearch=clear_es,
            clear_neo4j=clear_graph,
        )
        failed_dbs = [db for db, success in clear_results.items() if not success]
        if failed_dbs:
            logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        else:
            logger.info("All requested databases cleared successfully.")

    # 2. Load failures if needed
    failure_targets: Dict[str, Set[str]] = {}
    if args.retry_failures:
        seeded_failures = PipelineTracker.load_failures(args.failures_file)
        failure_targets = _group_failures_by_type(seeded_failures)
        tracker.seed_failures(seeded_failures)

    # 3. Process each requested file type
    for file_type in file_types:
        include_only = failure_targets.get(file_type) if args.retry_failures else None

        # If retrying failures and this type has none, skip it
        if args.retry_failures and not include_only:
            logger.info("No recorded failures for %s, skipping.", file_type)
            continue

        process_file_type(
            file_type,
            limit=args.limit,
            offset=args.offset,
            include_only=include_only,
            graph_rag_only=args.graph_rag_only,
            skip_graph=args.skip_graph,
            es_only=args.es_only,
            qdrant_only=args.qdrant_only,
            skip_es=args.skip_es,
            skip_qdrant=args.skip_qdrant,
            run_semantic_linking=not args.no_semantic_linking,
            run_community_detection=args.community_detection,
            run_topic_extraction=args.topic_extraction,
            run_citation_linking=args.citation_linking,
            run_temporal_linking=args.temporal_linking,
            run_entity_cooccurrence=args.entity_cooccurrence,
            invalidate_cache=args.invalidCache,
        )

    tracker.log_phase_end("NEFAC Document Ingestion Pipeline")
    tracker.log_summary()
    tracker.export_failures(args.failures_file)


if __name__ == "__main__":
    main()
