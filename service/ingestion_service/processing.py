# NOTE: Llama models are now managed via Ollama, not Hugging Face transformers. All Hugging Face Llama imports and code have been removed.
import os
import json
import logging
from dotenv import load_dotenv
from service.schemas.metadata import ContentMetadata, PDFMetadata, YouTubeMetadata
from .loader.pdf_loader import pdf_loader
from .loader.html_loader import html_loader
from .loader.youtube_loader import youtube_loader
from tqdm import tqdm
from service.ingestion_service.index.contextual_retrieval import (
    contextualize_and_index_documents,
)
from service.ingestion_service.index.graph_rag import graph_rag_ingest

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Contextualization Setup ---
# (Removed: contextual_prompt_template, OllamaLLM, and all local contextualization functions)


class LoaderService:
    def __init__(self, logger):
        self.logger = logger

    def load(self, file_type, metadata_json_path):
        if file_type == "pdf":
            return pdf_loader(
                metadata_json_path, "service/crawler/nefac_documents/documents"
            )
        elif file_type == "youtube":
            return youtube_loader(
                metadata_json_path, "service/crawler/nefac_documents/youtube"
            )
        elif file_type == "html":
            return html_loader(
                metadata_json_path, "service/crawler/nefac_documents/content"
            )
        else:
            self.logger.error(f"Unsupported file type: {file_type}")
            return []


class ChunkerService:
    def __init__(self, logger):
        self.logger = logger

    def chunk(self, documents, file_type, chunking_strategy=None):
        return documents


def main_pipeline(
    metadata_json_path,
    file_type,
    chunking_strategy=None,
    test_mode=False,
    embedding_model=None,
):
    logger = logging.getLogger("pipeline")
    loader = LoaderService(logger)
    chunker = ChunkerService(logger)

    logger.info(f"Starting processing for {metadata_json_path} of type {file_type}")
    documents = loader.load(file_type, metadata_json_path)
    if not documents:
        logger.warning(f"No documents loaded from {metadata_json_path}. Skipping.")
        return
    logger.info(f"Loaded {len(documents)} document chunks from {metadata_json_path}")
    chunked_documents = chunker.chunk(documents, file_type, chunking_strategy)
    logger.info(
        f"Created {len(chunked_documents)} chunks using {chunked_documents[0].metadata.get('chunking_strategy', 'unknown')} strategy"
    )

    # Graph RAG ingestion step
    logger.info("Starting Graph RAG ingestion into Neo4j knowledge graph...")
    graph_rag_ingest(chunked_documents)
    logger.info("Completed Graph RAG ingestion.")

    # Contextualize and index
    contextualized_documents = contextualize_and_index_documents(
        chunked_documents, embedding_model=embedding_model, test_mode=test_mode
    )
    logger.info(f"Completed ingestion and indexing for {metadata_json_path}")
    return len(contextualized_documents)


# Batch Pinecone upserts


def process_all_metadata(test_mode: bool = False):
    """
    Iterates over all metadata files in service/crawler/nefac_documents/metadata/ and processes all document types.
    Enforces Pydantic schema validation for all metadata entries.
    """
    metadata_dir = "service/crawler/nefac_documents/metadata/"

    # Map metadata files to types and schemas
    metadata_map = {
        "documents_metadata.json": (
            "pdf",
            PDFMetadata,
            "service/crawler/nefac_documents/documents",
        ),
        "youtube_metadata.json": (
            "youtube",
            YouTubeMetadata,
            "service/crawler/nefac_documents/youtube",
        ),
        "content_metadata.json": (
            "html",
            ContentMetadata,
            "service/crawler/nefac_documents/content",
        ),
    }

    for meta_file, (doc_type, schema, doc_dir) in metadata_map.items():
        meta_path = os.path.join(metadata_dir, meta_file)
        if not os.path.exists(meta_path):
            logger.warning(f"Metadata file {meta_path} not found. Skipping.")
            continue

        logger.info(f"Processing metadata file: {meta_path} as type {doc_type}")

        with open(meta_path, "r", encoding="utf-8") as f:
            try:
                entries = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {meta_path}: {e}")
                continue

        # Validate entries with Pydantic schema
        valid_entries = []
        for entry in tqdm(entries, desc=f"Validating {doc_type} entries"):
            try:
                validated_entry = schema(**entry)
                valid_entries.append(validated_entry.dict())
            except Exception as e:
                logger.error(
                    f"Schema validation failed for {doc_type} entry: {e}. Skipping entry."
                )

        if not valid_entries:
            logger.warning(f"No valid {doc_type} metadata entries found. Skipping.")
            continue

        # Process the validated entries
        main_pipeline(meta_path, doc_type, test_mode=test_mode)

    logger.info("Completed processing all metadata files")


if __name__ == "__main__":
    # Process all metadata in test mode
    process_all_metadata(test_mode=True)
