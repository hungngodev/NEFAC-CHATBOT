"""
NEFAC Document Ingestion Pipeline - Clean, Systematic Processing
Supports PDF, HTML, YouTube transcripts, and XLSX with intelligent processing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import argparse
import logging
import traceback
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document

from src.service.ingestion_service.index.database_cleaner import clear_all_databases
from src.service.ingestion_service.loader.unstructured_loader import unstructured_loader
from src.service.ingestion_service.progress_tracker import get_tracker, reset_tracker
from src.service.ingestion_service.settings import embedding_model, graph_llm_model

load_dotenv()

# Setup centralized logging
log_file = f"ingestion_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(message)s", datefmt="%H:%M:%S", handlers=[logging.FileHandler(log_file), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Supported file types (all handled by unified loader)
SUPPORTED_FILE_TYPES = ["pdf", "html", "youtube", "xlsx"]

# Resolve important directories relative to the backend folder for portability
BACKEND_DIR = Path(__file__).parents[3]
DOCS_BASE_DIR = BACKEND_DIR / "src/service/crawler/nefac_documents"


def get_metadata_path(file_type: str) -> str:
    """Return the metadata JSON path for the given file type."""
    return str(DOCS_BASE_DIR / "metadata" / f"{file_type}_metadata.json")


def graph_rag_ingest(documents: List[Document], file_type: str) -> None:
    if not documents:
        return

    tracker = get_tracker()
    tracker.log_pipeline_step("Graph RAG Ingestion", getattr(graph_llm_model, "model", str(graph_llm_model)))

    try:
        # Delegate Graph RAG ingestion to a single implementation to avoid drift
        from src.service.ingestion_service.index import graph_rag as graph_rag_index

        ingested_count = graph_rag_index.graph_rag_ingest(documents)
        tracker.track_db_upload(file_type, "Neo4j", ingested_count)

    except Exception as e:
        logger.error(f"Graph RAG ingestion failed: {e}")
        raise


def contextual_indexing(documents: List[Document], file_type: str) -> None:
    if not documents:
        return

    tracker = get_tracker()
    tracker.log_pipeline_step("Contextual Indexing", getattr(embedding_model, "model", str(embedding_model)))

    try:
        from src.service.ingestion_service.index.contextual_retrieval import save_contextual_elasticsearch_bm25_for_backend, upload_to_qdrant

        upload_to_qdrant(documents, embedding_model)
        tracker.track_db_upload(file_type, "Qdrant", len(documents))

        save_contextual_elasticsearch_bm25_for_backend(documents)
        tracker.track_db_upload(file_type, "Elasticsearch", len(documents))

    except Exception as e:
        logger.error(f"Contextual indexing failed: {e}")
        raise


def process_file_type(file_type: str, limit: Optional[int] = None, offset: int = 0) -> None:
    tracker = get_tracker()
    tracker.log_phase_start(f"Processing {file_type.upper()} files")

    try:
        metadata_path = get_metadata_path(file_type)
        documents_dir = str(DOCS_BASE_DIR / file_type)

        documents = unstructured_loader(metadata_path, documents_dir, limit, offset)

        if not documents:
            logger.warning(f"No documents found for {file_type}. Skipping.")
            return

        contextual_indexing(documents, file_type)
        graph_rag_ingest(documents, file_type)

    except Exception as e:
        logger.error(f"Failed processing {file_type}: {e}")
        traceback.print_exc()
    finally:
        tracker.log_phase_end(f"Processing {file_type.upper()} files")


def process_all_file_types(limit: Optional[int] = None, offset: int = 0, clear_databases: bool = False) -> None:
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
        process_file_type(file_type, limit, offset)

    tracker.log_phase_end("NEFAC Document Ingestion Pipeline")
    tracker.log_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument("--file-type", choices=SUPPORTED_FILE_TYPES + ["all"], default="all", help="Type of documents to process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--offset", type=int, default=0, help="Skip the first X documents")
    parser.add_argument("--clear", action="store_true", help="Clear existing database data before processing")
    args = parser.parse_args()

    if args.file_type == "all":
        process_all_file_types(limit=args.limit, offset=args.offset, clear_databases=args.clear)
    else:
        reset_tracker()
        tracker = get_tracker()
        if args.clear:
            logger.info("🧹 Clearing existing database data...")
            clear_all_databases()

        process_file_type(args.file_type, args.limit, args.offset)

        tracker.log_summary()


if __name__ == "__main__":
    main()
