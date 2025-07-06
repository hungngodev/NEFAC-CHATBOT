import logging
import os
from typing import Dict, List, Union

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from src.core.agents.tools.retrieval.metadata_filter import (
    filter_documents_by_metadata,
    prioritize_documents_by_metadata,
)
from src.load_env import load_env
from src.schemas.core_types import AgentState

# Optional: Qdrant for vector DB retrieval
try:
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
except ImportError:
    QdrantVectorStore = None
    QdrantClient = None
    print("Warning: langchain_qdrant or qdrant_client not installed. Qdrant vector DB retrieval will be skipped.")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")


def get_qdrant_retriever() -> object:
    """Return a Qdrant retriever for dense/semantic search."""
    if QdrantVectorStore is None or QdrantClient is None:
        raise ImportError("Qdrant dependencies not installed.")
    qdrant_url = os.environ["QDRANT_ENDPOINT"]
    collection_name = os.environ["QDRANT_CLUSTER_ID"]
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=qdrant_url, api_key=api_key)
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model,
    )
    return vectorstore.as_retriever()


def vector_retrieval_agent(state: AgentState) -> List[Document]:
    """
    Retrieves documents from Qdrant (dense vector store) and applies metadata filters and prioritization.
    Returns a list of Document objects.
    """
    try:
        question: str = state.transformed_query or ""
        filters: Dict[str, Union[str, int, float, bool, List[str]]] = state.metadata_filters or {}
        priorities: List[Dict[str, Union[str, int, float]]] = state.priorities or []

        qdrant_retriever = get_qdrant_retriever()

        # Perform initial retrieval from Qdrant
        retrieved_docs: List[Document] = qdrant_retriever.invoke(question)

        # Apply metadata filtering
        filtered_docs: List[Document] = filter_documents_by_metadata(retrieved_docs, filters)

        # Apply metadata prioritization
        prioritized_docs: List[Document] = prioritize_documents_by_metadata(filtered_docs, priorities)

        # Add a specific tag to the documents for easier identification in streaming
        for doc in prioritized_docs:
            doc.metadata["stream_tag"] = "vector_retrieved_docs"

        return prioritized_docs
    except Exception:
        return []
