"""
Keyword-based retrieval using ElasticSearch BM25.
Refactored to use the new modular approach with post-processing integration.
"""

import logging
import os
from typing import List

from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_core.documents import Document
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def get_bm25_retriever() -> ElasticSearchBM25Retriever:
    """Return an ElasticSearchBM25Retriever for sparse/keyword search."""
    try:
        elasticsearch_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]
        return ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)
    except KeyError as e:
        logger.error(f"Missing environment variable for ElasticSearch: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to create BM25 retriever: {e}")
        raise


@tool
def keyword_search(query: str, top_k: int = 10) -> List[Document]:
    """
    Performs a keyword-based search using ElasticSearch BM25.
    Ideal for queries with specific, exact terms, names, or legal citations.
    """
    logger.info(f"Executing keyword search for query: '{query}' with top_k={top_k}")
    try:
        retriever = get_bm25_retriever()
        # Pass top_k to the underlying retriever
        documents = retriever.invoke(query, top_k=top_k)

        # Add metadata tag for identification
        for doc in documents:
            if not hasattr(doc, "metadata") or doc.metadata is None:
                doc.metadata = {}
            doc.metadata["stream_tag"] = "keyword_retrieved_docs"
            doc.metadata["retrieval_method"] = "keyword_search"

        return documents
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []
