import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
import argparse
import logging
import sys
import traceback
from datetime import datetime
from typing import List, TypedDict, cast

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel
from tqdm import tqdm

# Try to import colorama for colored output, fallback gracefully if not available
try:
    from colorama import Back, Fore, Style, init

    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    # Create dummy color classes if colorama is not available
    class DummyColor:
        def __getattr__(self, name):
            return ""

    Fore = Back = Style = DummyColor()
    COLORS_AVAILABLE = False

# Try to import PDF validation tools
try:
    import pikepdf

    PDF_VALIDATION_AVAILABLE = True
except ImportError:
    PDF_VALIDATION_AVAILABLE = False

from src.service.ingestion_service.index.contextual_retrieval import (
    contextualize_and_index_documents,
)
from src.service.ingestion_service.index.database_cleaner import clear_all_databases
from src.service.ingestion_service.index.graph_rag import graph_rag_ingest
from src.service.ingestion_service.loader.unstructured_loader import unstructured_loader
from src.service.ingestion_service.settings import embedding_model

load_dotenv()


# Custom logging formatter with colors and better formatting
class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors and better structure to log messages."""

    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Get color for log level
        color = self.COLORS.get(record.levelname, "")

        # Format the message
        if record.levelname == "INFO":
            formatted_msg = f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {color}ℹ️  {record.getMessage()}{Style.RESET_ALL}"
        elif record.levelname == "WARNING":
            formatted_msg = f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {color}⚠️  {record.getMessage()}{Style.RESET_ALL}"
        elif record.levelname == "ERROR":
            formatted_msg = f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {color}❌ {record.getMessage()}{Style.RESET_ALL}"
        elif record.levelname == "CRITICAL":
            formatted_msg = f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {color}🚨 {record.getMessage()}{Style.RESET_ALL}"
        else:
            formatted_msg = f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {color}{record.getMessage()}{Style.RESET_ALL}"

        return formatted_msg


# Setup logging with custom formatter
def setup_logging():
    """Setup logging with custom colored formatter."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler with custom formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    return logger


# Initialize logging
logger = setup_logging()


# Utility functions for pretty printing
def print_header(title: str, subtitle: str = None):
    """Print a beautiful header with title and optional subtitle."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}{Style.RESET_ALL}")
    if subtitle:
        print(f"{Fore.CYAN}  {subtitle}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*60}{Style.RESET_ALL}\n")


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}📋 {title}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * (len(title) + 4)}{Style.RESET_ALL}")


def print_success(message: str):
    """Print a success message."""
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Fore.BLUE}ℹ️  {message}{Style.RESET_ALL}")


def print_progress(message: str):
    """Print a progress message."""
    print(f"{Fore.CYAN}🔄 {message}{Style.RESET_ALL}")


def print_step(step: int, total: int, message: str):
    """Print a step message with progress indicator."""
    print(f"{Fore.MAGENTA}📝 Step {step}/{total}: {message}{Style.RESET_ALL}")


def print_summary(title: str, items: dict):
    """Print a summary with key-value pairs."""
    print(f"\n{Fore.GREEN}{Style.BRIGHT}📊 {title}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'─' * (len(title) + 4)}{Style.RESET_ALL}")
    for key, value in items.items():
        print(f"  {Fore.CYAN}{key}:{Style.RESET_ALL} {value}")


def validate_pdf_file(file_path: str) -> tuple[bool, str]:
    """Validate if a PDF file is readable and not corrupted.

    Returns:
        tuple: (is_valid, error_message)
    """
    if not PDF_VALIDATION_AVAILABLE:
        return True, "PDF validation not available (pikepdf not installed)"

    try:
        with pikepdf.open(file_path) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                return False, "PDF has no pages"
            return True, f"Valid PDF with {page_count} pages"
    except pikepdf.PdfError as e:
        return False, f"PDF is corrupted or invalid: {str(e)}"
    except Exception as e:
        return False, f"Error reading PDF: {str(e)}"


def check_pdf_files_in_directory(directory: str, metadata_path: str) -> dict:
    """Check all PDF files in a directory for validity.

    Returns:
        dict: Statistics about PDF validation results
    """
    import json
    import os

    stats = {"total_files": 0, "valid_files": 0, "corrupted_files": 0, "corrupted_file_list": []}

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            filename = entry.get("filename")
            if not filename:
                continue

            file_path = os.path.join(directory, filename)
            if not os.path.exists(file_path):
                continue

            if filename.lower().endswith(".pdf"):
                stats["total_files"] += 1
                is_valid, error_msg = validate_pdf_file(file_path)

                if is_valid:
                    stats["valid_files"] += 1
                else:
                    stats["corrupted_files"] += 1
                    stats["corrupted_file_list"].append({"filename": filename, "error": error_msg})

    except Exception as e:
        print_error(f"Error checking PDF files: {e}")

    return stats


# Centralized file type configuration
SUPPORTED_FILE_TYPES = {
    "pdf": {"directory": "pdf", "metadata_file": "pdf_metadata.json", "description": "PDF documents"},
    "html": {"directory": "html", "metadata_file": "html_metadata.json", "description": "HTML documents"},
    "youtube": {"directory": "youtube", "metadata_file": "youtube_metadata.json", "description": "YouTube transcript documents"},
    "xlsx": {"directory": "xlsx", "metadata_file": "xlsx_metadata.json", "description": "Excel spreadsheet documents"},
}


# Helper functions for file type operations
def get_supported_file_types():
    """Get list of all supported file types."""
    return list(SUPPORTED_FILE_TYPES.keys())


def get_file_type_config(file_type: str):
    """Get configuration for a specific file type."""
    return SUPPORTED_FILE_TYPES.get(file_type)


def is_supported_file_type(file_type: str) -> bool:
    """Check if a file type is supported."""
    return file_type in SUPPORTED_FILE_TYPES


def get_file_type_directory(file_type: str) -> str:
    """Get the directory name for a file type."""
    config = get_file_type_config(file_type)
    return config["directory"] if config else None


def get_file_type_metadata_file(file_type: str) -> str:
    """Get the metadata file name for a file type."""
    config = get_file_type_config(file_type)
    return config["metadata_file"] if config else None


def get_file_type_description(file_type: str) -> str:
    """Get the description for a file type."""
    config = get_file_type_config(file_type)
    return config["description"] if config else "Unknown file type"


def get_all_file_type_descriptions() -> str:
    """Get a formatted string of all supported file types with descriptions."""
    descriptions = []
    for file_type, config in SUPPORTED_FILE_TYPES.items():
        descriptions.append(f"  {file_type}: {config['description']}")
    return "\n".join(descriptions)


class LoaderService:
    """Service class for loading documents of different types using the unified unstructured_loader.

    This replaces the previous separate html_loader, pdf_loader, and youtube_loader with a single
    unified loader that handles all document types (PDF, HTML, YouTube transcripts, XLSX, DOCX, etc.).
    """

    def __init__(self, logger, base_dir=None, base_metadata_dir=None):
        self.logger = logger
        # Use absolute path to nefac_documents directory if not provided
        if base_dir is None:
            base_dir = "/Users/hung/Documents/coding/build/NEFAC_CHATBOT/backend/src/service/crawler/nefac_documents"
        self.base_dir = base_dir

        # Define default metadata paths if not provided
        if base_metadata_dir is None:
            base_metadata_dir = self.base_dir + "/metadata"

        # Build metadata paths using centralized configuration
        self.default_metadata_paths = {}
        for file_type, config in SUPPORTED_FILE_TYPES.items():
            self.default_metadata_paths[file_type] = f"{base_metadata_dir}/{config['metadata_file']}"

    def get_default_metadata_path(self, file_type):
        """Get the default metadata path for a given file type."""
        return self.default_metadata_paths.get(file_type)

    def load(self, file_type, metadata_json_path=None, limit=None):
        """Load documents using the unified unstructured_loader for all file types.

        The unified loader automatically detects document types and handles:
        - PDF files (with table structure inference)
        - HTML files
        - YouTube transcript files (with timestamp parsing)
        - XLSX/DOCX files
        - Generic text files

        Args:
            file_type: The type of documents ('pdf', 'html', 'youtube', 'xlsx') - used for directory selection
            metadata_json_path: Path to the metadata JSON file
            limit: Optional limit on number of documents to process

        Returns:
            List[Document]: Processed documents with unified metadata structure
        """
        # Validate file type
        if not is_supported_file_type(file_type):
            error_msg = f"Unsupported file type: {file_type}. Supported types: {get_supported_file_types()}"
            print_error(error_msg)
            self.logger.error(error_msg)
            return []

        # Use default metadata path if none provided
        if metadata_json_path is None:
            metadata_json_path = self.get_default_metadata_path(file_type)
            if not metadata_json_path:
                error_msg = f"No default metadata path configured for file type: {file_type}"
                print_error(error_msg)
                self.logger.error(error_msg)
                return []

        print_progress(f"Loading {file_type} documents from {metadata_json_path}")
        self.logger.info(f"Starting to load documents of type '{file_type}' from {metadata_json_path}")

        # Get the appropriate directory for this file type using centralized config
        subdir = get_file_type_directory(file_type)
        if not subdir:
            error_msg = f"Could not determine directory for file type: {file_type}"
            print_error(error_msg)
            self.logger.error(error_msg)
            return []

        documents_dir = f"{self.base_dir}/{subdir}"

        # Pre-validate PDF files if this is a PDF processing run
        if file_type == "pdf" and PDF_VALIDATION_AVAILABLE:
            print_progress("Validating PDF files before processing...")
            pdf_stats = check_pdf_files_in_directory(documents_dir, metadata_json_path)

            if pdf_stats["corrupted_files"] > 0:
                print_warning(f"Found {pdf_stats['corrupted_files']} corrupted PDF files out of {pdf_stats['total_files']} total")
                print_section("Corrupted PDF Files")
                for corrupted_file in pdf_stats["corrupted_file_list"]:
                    print_error(f"  {corrupted_file['filename']}: {corrupted_file['error']}")

                if pdf_stats["valid_files"] == 0:
                    print_error("No valid PDF files found. Processing will likely fail.")
                    return []
                else:
                    print_info(f"Proceeding with {pdf_stats['valid_files']} valid PDF files")

        docs = []

        try:
            # Use the unified unstructured_loader for all file types
            docs = unstructured_loader(metadata_json_path, documents_dir, limit=limit)

            success_msg = f"Successfully loaded {len(docs)} documents of type '{file_type}' from {metadata_json_path}"
            print_success(success_msg)
            self.logger.info(success_msg)
        except Exception as e:
            error_msg = f"Error loading {file_type} documents: {e}"
            print_error(error_msg)
            self.logger.error(error_msg)

            # Provide more specific error information for PDF issues
            if file_type == "pdf" and "PDF" in str(e).upper():
                print_info("💡 Tip: This might be due to corrupted PDF files. Consider:")
                print_info("  1. Re-downloading the problematic PDF files")
                print_info("  2. Using PDF repair tools")
                print_info("  3. Converting PDFs to a different format")

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
    print_section(f"Processing {file_type.upper()} Documents")
    logger.info(f"Starting main pipeline for file_type='{file_type}', metadata_json_path='{metadata_json_path}', limit={limit}")

    # 3. Graph RAG ingest step
    def graph_rag_runnable(docs: List[Document]) -> List[Document]:
        print_progress(f"Starting Graph RAG ingestion for {len(docs)} documents...")
        logger.info(f"[GraphRAG] Starting graph RAG ingestion for {len(docs)} documents...")
        tqdm.write(f"{Fore.CYAN}[GraphRAG] Ingesting {len(docs)} documents into Neo4j knowledge graph...{Style.RESET_ALL}")
        graph_rag_ingest(docs)
        print_success(f"Graph RAG ingestion completed for {len(docs)} documents")
        logger.info("[GraphRAG] Completed graph RAG ingestion.")
        tqdm.write(f"{Fore.GREEN}[GraphRAG] Graph RAG ingestion complete.{Style.RESET_ALL}")
        return docs  # Pass through for next step

    # 4. Indexing step
    def index_runnable(docs: List[Document]) -> List[Document]:
        print_progress(f"Starting contextual retriever indexing for {len(docs)} documents...")
        logger.info(f"[Indexing] Starting contextual retriever indexing for {len(docs)} documents...")
        tqdm.write(f"{Fore.CYAN}[Indexing] Indexing {len(docs)} documents into Qdrant and Elasticsearch...{Style.RESET_ALL}")
        contextualize_and_index_documents(docs, embedding_model=embedding_model)
        print_success(f"Contextual retriever indexing completed for {len(docs)} documents")
        logger.info("[Indexing] Completed contextual retriever indexing.")
        tqdm.write(f"{Fore.GREEN}[Indexing] Contextual retriever indexing complete.{Style.RESET_ALL}")
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

    print_progress("Invoking pipeline with parallel execution...")
    logger.info("[Pipeline] Invoking pipeline...")
    tqdm.write(f"{Fore.MAGENTA}[Pipeline] Invoking pipeline with parallel execution...{Style.RESET_ALL}")

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
        error_msg = f"Pipeline did not return expected result dict: {results}"
        print_error(error_msg)
        logger.error(error_msg)
        tqdm.write(f"{Fore.RED}[Pipeline] ERROR: {error_msg}{Style.RESET_ALL}")
        return 0

    if not results["index"]:  # type: ignore
        warning_msg = f"No documents processed for {metadata_json_path}. Skipping."
        print_warning(warning_msg)
        logger.warning(warning_msg)
        tqdm.write(f"{Fore.YELLOW}[Pipeline] WARNING: {warning_msg}{Style.RESET_ALL}")
        return 0

    # --- TEMP: Print Chunk Example ---
    if results["index"]:
        import json

        print("\n\n" + "=" * 25 + " CHUNK EXAMPLE " + "=" * 25)
        example_chunk = results["index"][0]
        print("--- METADATA ---")
        # Use json.dumps for pretty printing the metadata dictionary
        print(json.dumps(example_chunk.metadata, indent=2, default=str))
        print("\n--- CONTENT ---")
        print(example_chunk.page_content)
        print("=" * 65 + "\n\n")
    # --- END TEMP ---

    success_msg = f"Completed ingestion and indexing for {metadata_json_path}"
    print_success(success_msg)
    logger.info(success_msg)
    tqdm.write(f"{Fore.GREEN}[Pipeline] {success_msg}{Style.RESET_ALL}")
    return len(results["index"])  # type: ignore


def process_all_file_types(limit=None, clear_databases=True):
    """Process all file types in sequence using LoaderService and main_pipeline function"""
    logger = logging.getLogger("pipeline")

    # Clear all databases before starting if requested
    if clear_databases:
        print_header("Clearing all existing database data")
        logger.info("Clearing all existing database data before processing")
        clear_results = clear_all_databases()

        # Check if any database clearing failed
        failed_dbs = [db for db, success in clear_results.items() if not success]
        if failed_dbs:
            print_warning(f"Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
            logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        else:
            print_success("Successfully cleared all databases")
            logger.info("Successfully cleared all databases")
        print_section("Processing Complete")

    loader_service = LoaderService(logger)

    # Use centralized file type configuration
    file_types = get_supported_file_types()

    total_processed = 0
    with tqdm(total=len(file_types), desc="Processing file types", colour="cyan") as pbar:
        for file_type in file_types:
            pbar.set_description(f"Processing {file_type}")

            # Get default metadata path from LoaderService
            metadata_path = loader_service.get_default_metadata_path(file_type)
            print_step(1, len(file_types), f"Processing {file_type} files...")
            logger.info(f"Processing {file_type} files from {metadata_path}")

            try:
                processed_count = main_pipeline(
                    metadata_path,
                    file_type,
                    limit,
                )
                total_processed += processed_count
                print_success(f"Completed {file_type}: {processed_count} documents")
                logger.info(f"Successfully processed {processed_count} {file_type} documents")
            except Exception as e:
                print_error(f"Failed processing {file_type}: {e}")
                logger.error(f"Failed processing {file_type}: {e}")

            pbar.update(1)

    # Print final summary
    print_header("Processing Complete", f"Total documents processed: {total_processed}")
    print_summary("Final Results", {"Total file types processed": len(file_types), "Total documents processed": total_processed, "File types": ", ".join(file_types)})

    return total_processed


def clear_databases_only():
    """Standalone function to only clear databases without processing any documents"""
    logger = logging.getLogger("pipeline")
    print_header("Clearing all existing database data")
    logger.info("Clearing all existing database data")

    clear_results = clear_all_databases()

    # Check results and provide feedback
    failed_dbs = [db for db, success in clear_results.items() if not success]
    if failed_dbs:
        print_warning(f"Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
        logger.warning(f"Failed to clear databases: {', '.join(failed_dbs)}")
        return False
    else:
        print_success("Successfully cleared all databases")
        logger.info("Successfully cleared all databases")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEFAC Document Ingestion Pipeline")
    parser.add_argument("--file-type", choices=get_supported_file_types() + ["all"], default="all", help=f"Type of documents to process. Supported types:\n{get_all_file_type_descriptions()}")
    parser.add_argument("--metadata-path", help="Path to metadata JSON file (optional - uses default paths when not provided)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process (for testing)")
    parser.add_argument("--no-clear", action="store_true", help="Skip clearing existing database data before processing")
    parser.add_argument("--clear-only", action="store_true", help="Only clear databases without processing any documents")
    parser.add_argument("--validate-pdfs", action="store_true", help="Only validate PDF files without processing them")

    args = parser.parse_args()

    # Handle clear-only mode
    if args.clear_only:
        print_header("Clear-only mode")
        print_info("Clearing databases without processing documents...")
        success = clear_databases_only()
        sys.exit(0 if success else 1)

    # Handle PDF validation mode
    if args.validate_pdfs:
        print_header("PDF Validation Mode")
        print_info("Validating PDF files without processing them...")

        if not PDF_VALIDATION_AVAILABLE:
            print_error("PDF validation not available. Please install pikepdf: pip install pikepdf")
            sys.exit(1)

        # Get PDF metadata path
        loader_service = LoaderService(logging.getLogger("pipeline"))
        pdf_metadata_path = loader_service.get_default_metadata_path("pdf")
        if not pdf_metadata_path:
            print_error("No default PDF metadata path configured")
            sys.exit(1)

        pdf_dir = f"{loader_service.base_dir}/pdf"
        print_info(f"Checking PDF files in: {pdf_dir}")

        pdf_stats = check_pdf_files_in_directory(pdf_dir, pdf_metadata_path)

        print_summary(
            "PDF Validation Results",
            {"Total PDF files": pdf_stats["total_files"], "Valid files": pdf_stats["valid_files"], "Corrupted files": pdf_stats["corrupted_files"], "Success rate": f"{(pdf_stats['valid_files'] / pdf_stats['total_files'] * 100):.1f}%" if pdf_stats["total_files"] > 0 else "N/A"},
        )

        if pdf_stats["corrupted_files"] > 0:
            print_section("Corrupted PDF Files")
            for corrupted_file in pdf_stats["corrupted_file_list"]:
                print_error(f"  {corrupted_file['filename']}: {corrupted_file['error']}")

        sys.exit(0 if pdf_stats["corrupted_files"] == 0 else 1)

    print_header("NEFAC ingestion pipeline")
    print_info(f"📄 File type: {args.file_type}")
    if args.file_type != "all":
        print_info(f"📝 Description: {get_file_type_description(args.file_type)}")
    if args.metadata_path:
        print_info(f"📁 Metadata path: {args.metadata_path}")
    if args.limit:
        print_info(f"🔢 Document limit: {args.limit}")
    if args.no_clear:
        print_warning("Will append to existing database data")
    else:
        print_info("Will clear existing database data first")
    print_section("Processing Start")

    start_time = datetime.now()
    try:
        if args.file_type == "all":
            total_processed = process_all_file_types(
                limit=args.limit,
                clear_databases=not args.no_clear,
            )
            end_time = datetime.now()
            duration = end_time - start_time
            print_header("Pipeline Complete", f"Successfully processed {total_processed} total documents across all file types!")
            print_summary("Performance", {"Start time": start_time.strftime("%H:%M:%S"), "End time": end_time.strftime("%H:%M:%S"), "Duration": str(duration).split(".")[0]})  # Remove microseconds
        else:
            # Validate file type
            if not is_supported_file_type(args.file_type):
                print_error(f"Unsupported file type: {args.file_type}")
                print_info(f"Supported file types:\n{get_all_file_type_descriptions()}")
                sys.exit(1)

            # Use default metadata path if not provided, just like the "all" option
            metadata_path = args.metadata_path
            if not metadata_path:
                loader_service = LoaderService(logging.getLogger("pipeline"))
                metadata_path = loader_service.get_default_metadata_path(args.file_type)
                if not metadata_path:
                    print_error(f"No default metadata path configured for file type: {args.file_type}")
                    sys.exit(1)
                print_info(f"📁 Using default metadata path: {metadata_path}")

            # Clear databases before processing individual file type if requested
            if not args.no_clear:
                print_header("Clearing all existing database data")
                clear_results = clear_all_databases()
                failed_dbs = [db for db, success in clear_results.items() if not success]
                if failed_dbs:
                    print_warning(f"Warning: Failed to clear some databases: {', '.join(failed_dbs)}")
                else:
                    print_success("Successfully cleared all databases")
                print_section("Processing Complete")

            processed_count = main_pipeline(
                metadata_json_path=metadata_path,
                file_type=args.file_type,
                limit=args.limit,
            )
            end_time = datetime.now()
            duration = end_time - start_time
            print_header("Pipeline Complete", f"Successfully processed {processed_count} documents!")
            print_summary("Results", {"File type": args.file_type, "Documents processed": processed_count, "Metadata path": metadata_path})
            print_summary("Performance", {"Start time": start_time.strftime("%H:%M:%S"), "End time": end_time.strftime("%H:%M:%S"), "Duration": str(duration).split(".")[0]})  # Remove microseconds
    except Exception as e:
        print_error(f"Pipeline failed: {e}")

        # Provide specific guidance for PDF-related errors
        if "pdf" in args.file_type.lower() and any(keyword in str(e).lower() for keyword in ["pdf", "corrupt", "invalid", "trailer", "xref"]):
            print_section("PDF Processing Troubleshooting")
            print_info("This error appears to be related to PDF processing issues. Here are some suggestions:")
            print_info("1. Run PDF validation first: python processing.py --validate-pdfs")
            print_info("2. Check if PDF files are corrupted or password-protected")
            print_info("3. Try processing individual file types: python processing.py --file-type html")
            print_info("4. Consider re-downloading or repairing the problematic PDF files")

        traceback.print_exc()
