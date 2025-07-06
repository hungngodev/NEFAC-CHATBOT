import os
from typing import Dict, List, Union

from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_core.documents import Document

from src.core.agents.tools.retrieval.metadata_filter import (
    filter_documents_by_metadata,
    prioritize_documents_by_metadata,
)
from src.load_env import load_env
from src.schemas.core_types import AgentState

load_env()


def get_bm25_retriever() -> object:
    """Return an ElasticSearchBM25Retriever for sparse/keyword search."""
    elasticsearch_url = os.environ["ES_HOST"]
    index_name = os.environ["ES_INDEX"]
    return ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)


def keyword_retrieval_agent(state: AgentState) -> List[Document]:
    """
    Retrieves documents from ElasticSearch BM25 (sparse keyword store) and applies metadata filters and prioritization.
    Returns a list of Document objects.
    """
    try:
        question: str = state.transformed_query or ""
        filters: Dict[str, Union[str, int, float, bool, List[str]]] = state.metadata_filters or {}
        priorities: List[Dict[str, Union[str, int, float]]] = state.priorities or []

        bm25_retriever = get_bm25_retriever()

        # Perform initial retrieval from BM25
        retrieved_docs: List[Document] = bm25_retriever.invoke(question)

        # Apply metadata filtering
        filtered_docs: List[Document] = filter_documents_by_metadata(retrieved_docs, filters)

        # Apply metadata prioritization
        prioritized_docs: List[Document] = prioritize_documents_by_metadata(filtered_docs, priorities)

        # Add a specific tag to the documents for easier identification in streaming
        for doc in prioritized_docs:
            doc.metadata["stream_tag"] = "keyword_retrieved_docs"

        return prioritized_docs
    except Exception:
        return []
