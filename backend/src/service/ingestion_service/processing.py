# NOTE: Llama models are now managed via Ollama, not Hugging Face transformers. All Hugging Face Llama imports and code have been removed.
import logging
from typing import Any, List, TypedDict, cast

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from tqdm import tqdm

from src.config.constant import MODEL_NAME, QUERY_TRANSLATION_MODEL_NAME
from src.service.ingestion_service.index.contextual_retrieval import (
    contextualize_and_index_documents,
)
from src.service.ingestion_service.index.graph_rag import graph_rag_ingest
from src.service.ingestion_service.loader.html_loader import html_loader
from src.service.ingestion_service.loader.pdf_loader import pdf_loader
from src.service.ingestion_service.loader.youtube_loader import youtube_loader

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Ollama Models for Ingestion Pipeline ---

# LLM for context/summary generation (Llama 70B)
ollama_llm = OllamaLLM(model=MODEL_NAME)
# Embedding model for chunk embeddings (Qwen3:8b)
ollama_embedding_model = OllamaEmbeddings(model=QUERY_TRANSLATION_MODEL_NAME)


class LoaderService:
    def __init__(self, logger):
        self.logger = logger

    def load(self, file_type, metadata_json_path):
        self.logger.info(f"Starting to load documents of type '{file_type}' from {metadata_json_path}")
        docs = []
        if file_type == "pdf":
            docs = pdf_loader(metadata_json_path, "service/crawler/nefac_documents/documents")
        elif file_type == "youtube":
            docs = youtube_loader(metadata_json_path, "service/crawler/nefac_documents/youtube")
        elif file_type == "html":
            docs = html_loader(metadata_json_path, "service/crawler/nefac_documents/content")
        else:
            self.logger.error(f"Unsupported file type: {file_type}")
            return []
        self.logger.info(f"Loaded {len(docs)} documents of type '{file_type}' from {metadata_json_path}")
        return docs


def loader_runnable(file_type: str, metadata_json_path: str) -> List[Document]:
    loader = LoaderService(logging.getLogger("pipeline"))
    docs = loader.load(file_type, metadata_json_path)
    # Convert to Document objects if needed
    return docs


class PipelineInput(TypedDict):
    file_type: str
    metadata_json_path: str


def main_pipeline(
    metadata_json_path,
    file_type,
    test_mode=False,
):
    logger = logging.getLogger("pipeline")
    logger.info(f"Starting main pipeline for file_type='{file_type}', metadata_json_path='{metadata_json_path}'")

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
        contextualize_and_index_documents(docs, embedding_model=ollama_embedding_model, test_mode=test_mode)
        logger.info("[Indexing] Completed contextual retriever indexing.")
        tqdm.write("[Indexing] Contextual retriever indexing complete.")
        return docs

    # 5. Compose the pipeline with parallel execution for graph RAG and indexing
    pipeline = RunnableLambda(
        lambda args: loader_runnable(
            cast(PipelineInput, args)["file_type"],
            cast(PipelineInput, args)["metadata_json_path"],
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
    results: Any = pipeline.invoke({"file_type": file_type, "metadata_json_path": metadata_json_path})
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
