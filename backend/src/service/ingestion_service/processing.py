# NOTE: Llama models are now managed via Ollama, not Hugging Face transformers. All Hugging Face Llama imports and code have been removed.
import logging
from typing import List, TypedDict, cast

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel
from tqdm import tqdm

from src.service.ingestion_service.database_cleaner import clear_all_databases
from src.service.ingestion_service.index.contextual_retrieval import (
    contextualize_and_index_documents,
)
from src.service.ingestion_service.index.graph_rag import graph_rag_ingest
from src.service.ingestion_service.loader.html_loader import html_loader
from src.service.ingestion_service.loader.pdf_loader import pdf_loader
from src.service.ingestion_service.loader.youtube_loader import youtube_loader
from src.service.ingestion_service.settings import embedding_model

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LoaderService:
    """Service class for loading documents of different types using appropriate loaders."""

    def __init__(self, logger, base_dir=None, base_metadata_dir=None):
        self.logger = logger
        # Use absolute path to nefac_documents directory if not provided
        if base_dir is None:
            base_dir = "/Users/hung/Documents/coding/build/NEFAC_CHATBOT/resource/nefac_documents"
        self.base_dir = base_dir

        # Define subdirectories for different file types
        self.type_directories = {"pdf": "documents", "youtube": "youtube", "html": "content"}

        # Define default metadata paths if not provided
        if base_metadata_dir is None:
            base_metadata_dir = "/Users/hung/Documents/coding/build/NEFAC_CHATBOT/resource/nefac_documents/metadata"

        self.default_metadata_paths = {
            "html": f"{base_metadata_dir}/content_metadata.json",
            "pdf": f"{base_metadata_dir}/documents_metadata.json",
            "youtube": f"{base_metadata_dir}/youtube_metadata.json",
        }

    def get_default_metadata_path(self, file_type):
        """Get the default metadata path for a given file type."""
        return self.default_metadata_paths.get(file_type)

    def load(self, file_type, metadata_json_path=None, limit=None):
        """Load documents using the appropriate loader for the file type."""
        # Use default metadata path if none provided
        if metadata_json_path is None:
            metadata_json_path = self.get_default_metadata_path(file_type)
            if not metadata_json_path:
                self.logger.error(f"No default metadata path configured for file type: {file_type}")
                return []

        self.logger.info(f"Starting to load documents of type '{file_type}' from {metadata_json_path}")

        # Get the appropriate directory for this file type
        subdir = self.type_directories.get(file_type)
        if not subdir:
            self.logger.error(f"Unsupported file type: {file_type}")
            return []

        documents_dir = f"{self.base_dir}/{subdir}"
        docs = []

        try:
            if file_type == "pdf":
                docs = pdf_loader(metadata_json_path, documents_dir, limit=limit)
            elif file_type == "youtube":
                docs = youtube_loader(metadata_json_path, documents_dir, limit=limit)
            elif file_type == "html":
                docs = html_loader(metadata_json_path, documents_dir, limit=limit)

            self.logger.info(f"Successfully loaded {len(docs)} documents of type '{file_type}' from {metadata_json_path}")
        except Exception as e:
            self.logger.error(f"Error loading {file_type} documents: {e}")
            docs = []

        return docs


def loader_runnable(file_type: str, metadata_json_path: str, limit: int = None) -> List[Document]:
    """Load documents using the appropriate loader for the file type."""
    loader = LoaderService(logging.getLogger("pipeline"))
    docs = loader.load(file_type, metadata_json_path, limit=limit)

    if limit and limit > 0:
        logging.getLogger("pipeline").info(f"Loaded {len(docs)} documents (limit={limit})")

    return docs


class PipelineInput(TypedDict):
    file_type: str
    metadata_json_path: str
    limit: int


def main_pipeline(
    metadata_json_path,
    file_type,
    limit=None,
):
    """Main ingestion pipeline for processing documents into databases."""
    logger = logging.getLogger("pipeline")
    logger.info(f"Starting main pipeline for file_type='{file_type}', metadata_json_path='{metadata_json_path}', limit={limit}")

    # 3. Graph RAG ingest step
    def graph_rag_runnable(docs: List[Document]) -> List[Document]:
        logger.info(f"[GraphRAG] Starting graph RAG ingestion for {len(docs)} documents...")
        tqdm.write(f"[GraphRAG] Ingesting {len(docs)} documents into Neo4j knowledge graph...")
        graph_rag_ingest(docs)
        logger.info("[GraphRAG] Completed graph RAG ingestion.")
        tqdm.write("[GraphRAG] Graph RAG ingestion complete.")
        return docs  # Pass through for next step

    # 4. Indexing step
    def index_runnable(docs: List[Document]) -> List[Document]:
        logger.info(f"[Indexing] Starting contextual retriever indexing for {len(docs)} documents...")
        tqdm.write(f"[Indexing] Indexing {len(docs)} documents into Qdrant and Elasticsearch...")
        contextualize_and_index_documents(docs, embedding_model=embedding_model)
        logger.info("[Indexing] Completed contextual retriever indexing.")
        tqdm.write("[Indexing] Contextual retriever indexing complete.")
        return docs

    # 5. Compose the pipeline with parallel execution for graph RAG and indexing
    pipeline = RunnableLambda(
        lambda args: loader_runnable(
            cast(PipelineInput, args)["file_type"],
            cast(PipelineInput, args)["metadata_json_path"],
            cast(PipelineInput, args).get("limit"),
        )
    ) | RunnableParallel(
        {
            "graph_rag": RunnableLambda(graph_rag_runnable),
            "index": RunnableLambda(index_runnable),
        }
    )

    logger.info("[Pipeline] Invoking pipeline...")
    tqdm.write("[Pipeline] Invoking pipeline...")
    # Execute the pipeline
    results = pipeline.invoke(
        {
            "file_type": file_type,
            "metadata_json_path": metadata_json_path,
            "limit": limit,
        }
    )
    results = cast(dict, results)
    # Ensure results is a dict with 'index' and 'graph_rag' keys
    if not isinstance(results, dict) or "index" not in results or "graph_rag" not in results:
        logger.error(f"Pipeline did not return expected result dict: {results}")
        tqdm.write(f"[Pipeline] ERROR: Pipeline did not return expected result dict: {results}")
        return 0
    if not results["index"]:  # type: ignore
        logger.warning(f"No documents processed for {metadata_json_path}. Skipping.")
        tqdm.write(f"[Pipeline] WARNING: No documents processed for {metadata_json_path}. Skipping.")
        return 0
    logger.info(f"Completed ingestion and indexing for {metadata_json_path}")
    tqdm.write(f"[Pipeline] Completed ingestion and indexing for {metadata_json_path}")
    return len(results["index"])  # type: ignore


def process_all_file_types(limit=None, clear_databases=True):
    """Process all file types in sequence using LoaderService and main_pipeline function"""
    logger = logging.getLogger("pipeline")

    # Clear all databases before starting if requested
    if clear_databases:
        print("🧹 Clearing all existing database data...")
        logger.info("Clearing all existing database data before processing")
        clear_results = clear_all_databases()

        # Check if any database clearing failed
        failed_dbs = [db for db, success in clear_results.items() if not success]
        if failed_dbs:
            print(f"⚠️  Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
            logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        else:
            print("✅ Successfully cleared all databases")
            logger.info("Successfully cleared all databases")
        print("-" * 50)

    loader_service = LoaderService(logger)

    # Define supported file types - LoaderService now handles default metadata paths
    file_types = ["html", "pdf", "youtube"]

    total_processed = 0
    for file_type in file_types:
        # Get default metadata path from LoaderService
        metadata_path = loader_service.get_default_metadata_path(file_type)
        print(f"🚀 Processing {file_type} files...")
        logger.info(f"Processing {file_type} files from {metadata_path}")

        try:
            processed_count = main_pipeline(
                metadata_path,
                file_type,
                limit,
            )
            total_processed += processed_count
            print(f"✅ Completed {file_type}: {processed_count} documents\n")
            logger.info(f"Successfully processed {processed_count} {file_type} documents")
        except Exception as e:
            print(f"❌ Failed processing {file_type}: {e}\n")
            logger.error(f"Failed processing {file_type}: {e}")

    return total_processed


def clear_databases_only():
    """Standalone function to only clear databases without processing any documents"""
    logger = logging.getLogger("pipeline")
    print("🧹 Clearing all existing database data...")
    logger.info("Clearing all existing database data")

    clear_results = clear_all_databases()

    # Check results and provide feedback
    failed_dbs = [db for db, success in clear_results.items() if not success]
    if failed_dbs:
        print(f"⚠️  Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
        logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        return False
    else:
        print("✅ Successfully cleared all databases")
        logger.info("Successfully cleared all databases")
        return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument("--file-type", choices=["html", "pdf", "youtube", "all"], default="all", help="Type of documents to process")
    parser.add_argument("--metadata-path", help="Path to metadata JSON file (optional - uses default paths when not provided)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process (for testing)")
    parser.add_argument("--no-clear", action="store_true", help="Skip clearing existing database data before processing")
    parser.add_argument("--clear-only", action="store_true", help="Only clear databases without processing any documents")

    args = parser.parse_args()

    # Handle clear-only mode
    if args.clear_only:
        print("🧹 Clear-only mode: Clearing databases without processing documents...")
        success = clear_databases_only()
        exit(0 if success else 1)

    print("🚀 Starting NEFAC ingestion pipeline...")
    print(f"📄 File type: {args.file_type}")
    if args.metadata_path:
        print(f"📁 Metadata path: {args.metadata_path}")
    if args.limit:
        print(f"🔢 Document limit: {args.limit}")
    if args.no_clear:
        print("🔄 Will append to existing database data")
    else:
        print("🧹 Will clear existing database data first")
    print("-" * 50)

    try:
        if args.file_type == "all":
            total_processed = process_all_file_types(
                limit=args.limit,
                clear_databases=not args.no_clear,
            )
            print(f"✅ Successfully processed {total_processed} total documents across all file types!")
        else:
            # Use default metadata path if not provided, just like the "all" option
            metadata_path = args.metadata_path
            if not metadata_path:
                import logging

                from src.service.ingestion_service.processing import LoaderService

                loader_service = LoaderService(logging.getLogger("pipeline"))
                metadata_path = loader_service.get_default_metadata_path(args.file_type)
                if not metadata_path:
                    print(f"❌ No default metadata path configured for file type: {args.file_type}")
                    exit(1)
                print(f"📁 Using default metadata path: {metadata_path}")

            # Clear databases before processing individual file type if requested
            if not args.no_clear:
                print("🧹 Clearing all existing database data...")
                clear_results = clear_all_databases()
                failed_dbs = [db for db, success in clear_results.items() if not success]
                if failed_dbs:
                    print(f"⚠️  Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
                else:
                    print("✅ Successfully cleared all databases")
                print("-" * 50)

            processed_count = main_pipeline(
                metadata_json_path=metadata_path,
                file_type=args.file_type,
                limit=args.limit,
            )
            print(f"✅ Successfully processed {processed_count} documents!")
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback

        traceback.print_exc()
