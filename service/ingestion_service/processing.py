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
from service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel
from typing import List, TypedDict, Any, cast
from langchain_ollama import OllamaLLM
from langchain_ollama import OllamaEmbeddings

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Ollama Models for Ingestion Pipeline ---
# LLM for context/summary generation (Llama 70B)
ollama_llm = OllamaLLM(model="llama3:70b-instruct")
# Embedding model for chunk embeddings (Qwen3:8b)
ollama_embedding_model = OllamaEmbeddings(model="qwen3:8b")


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


def loader_runnable(file_type: str, metadata_json_path: str) -> List[Document]:
    loader = LoaderService(logging.getLogger("pipeline"))
    docs = loader.load(file_type, metadata_json_path)
    # Convert to Document objects if needed
    return [
        (
            Document(page_content=doc["text"], metadata=doc.get("metadata", {}))
            if not isinstance(doc, Document)
            else doc
        )
        for doc in docs
    ]


class PipelineInput(TypedDict):
    file_type: str
    metadata_json_path: str


def main_pipeline(
    metadata_json_path,
    file_type,
    chunking_strategy=None,
    test_mode=False,
):
    logger = logging.getLogger("pipeline")

    # Use the semantic double-pass splitter for chunking and contextualization
    context_prompt_template = ChatPromptTemplate.from_template(
        """<document>
{document}
</document>
Here is the chunk we want to situate within the whole document
<chunk>
{chunk}
</chunk>
Please generate a short succinct context summary to situate this text chunk within the overall document to enhance search retrieval, two or three sentences max. The chunk contains merged content from different document sections, so focus on the main topics and concepts rather than sequential flow. Answer only with the succinct context and nothing else."""
    )
    splitter = SemanticDoublePassMergingSplitterWithContext(
        embeddings=ollama_embedding_model,
        chat_model=ollama_llm,
        context_prompt_template=context_prompt_template,
    )

    # 3. Graph RAG ingest step
    def graph_rag_runnable(docs: List[Document]) -> List[Document]:
        graph_rag_ingest(docs)
        return docs  # Pass through for next step

    # 4. Indexing step
    def index_runnable(docs: List[Document]) -> List[Document]:
        contextualize_and_index_documents(
            docs, embedding_model=ollama_embedding_model, test_mode=test_mode
        )
        return docs

    # 5. Compose the pipeline with parallel execution for graph RAG and indexing
    pipeline = (
        RunnableLambda(
            lambda args: loader_runnable(
                cast(PipelineInput, args)["file_type"],
                cast(PipelineInput, args)["metadata_json_path"],
            )
        )
        | RunnableLambda(
            lambda docs: (
                splitter.split_documents(cast(List[Document], docs)) if docs else []
            )
        )
        | RunnableParallel(
            {
                "graph_rag": RunnableLambda(graph_rag_runnable),
                "index": RunnableLambda(index_runnable),
            }
        )
    )

    # Execute the pipeline
    results: Any = pipeline.invoke(
        {"file_type": file_type, "metadata_json_path": metadata_json_path}
    )
    results = cast(dict, results)
    # Ensure results is a dict with 'index' and 'graph_rag' keys
    if (
        not isinstance(results, dict)
        or "index" not in results
        or "graph_rag" not in results
    ):
        logger.error(f"Pipeline did not return expected result dict: {results}")
        return 0
    if not results["index"]:  # type: ignore
        logger.warning(f"No documents processed for {metadata_json_path}. Skipping.")
        return 0
    logger.info(f"Completed ingestion and indexing for {metadata_json_path}")
    return len(results["index"])  # type: ignore


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
