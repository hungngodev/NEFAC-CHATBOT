"""
Keyword-based retrieval using ElasticSearch BM25.
Refactored to use the new modular approach with post-processing integration.
"""

import os

from elasticsearch import Elasticsearch
from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_core.documents import Document
from langchain_core.tools import tool

elasticsearch_url = os.environ["ES_HOST"]
index_name = os.environ["ES_INDEX"]
print("ES_HOST =", os.environ.get("ES_HOST"))
print("ES_INDEX =", os.environ.get("ES_INDEX"))

# Initialize Elasticsearch client
es = Elasticsearch(elasticsearch_url)

if not es.indices.exists(index=index_name):
    # Create index and retriever if index doesn't exist
    keyword_retriever = ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)
else:
    # Just instantiate the retriever if index already exists
    keyword_retriever = ElasticSearchBM25Retriever(client=es, index_name=index_name)


@tool
def keyword_search(query: str, top_k: int = 10) -> list[Document]:
    """
    Performs a keyword-based search using ElasticSearch BM25.
    Ideal for queries with specific, exact terms, names, or legal citations.
    """
    retriever = keyword_retriever
    # Pass top_k to the underlying retriever
    documents = retriever.invoke(query, top_k=top_k)

    # Add metadata tag for identification
    for doc in documents:
        if not hasattr(doc, "metadata") or doc.metadata is None:
            doc.metadata = {}
        doc.metadata["stream_tag"] = "keyword_retrieved_docs"
        doc.metadata["retrieval_method"] = "keyword_search"

    return documents
