"""
Vector-based retrieval using Qdrant vector store.
Refactored to use the new modular approach with post-processing integration.
"""

import logging
import os
from typing import List

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings

# Optional: Qdrant for vector DB retrieval
try:
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
except ImportError:
    QdrantVectorStore = None
    QdrantClient = None
    logger = logging.getLogger(__name__)
    logger.warning("Qdrant dependencies not installed. Vector retrieval will be unavailable.")

logger = logging.getLogger(__name__)
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")


qdrant_url = os.environ["QDRANT_ENDPOINT"]
collection_name = os.environ["QDRANT_CLUSTER_ID"]
api_key = os.environ.get("QDRANT_API_KEY")

client = QdrantClient(url=qdrant_url, api_key=api_key)
vectorstore = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embedding_model,
)
vector_retriever = vectorstore.as_retriever()


@tool
def vector_search(query: str, top_k: int = 10) -> List[Document]:
    """
    Performs semantic search on a Qdrant vector store to find documents
    conceptually related to the query. Best for broad, conceptual questions.
    """
    logger.info(f"Executing vector search for query: '{query}' with top_k={top_k}")
    try:
        retriever = vector_retriever
        # Pass top_k to the underlying retriever
        documents = retriever.invoke(query, search_kwargs={"k": top_k})

        # Add metadata tag for identification
        for doc in documents:
            if not hasattr(doc, "metadata") or doc.metadata is None:
                doc.metadata = {}
            doc.metadata["stream_tag"] = "vector_retrieved_docs"
            doc.metadata["retrieval_method"] = "vector_search"

        return documents
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []
