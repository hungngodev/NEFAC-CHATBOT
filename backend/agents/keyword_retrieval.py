from typing import Any, Dict

from agents.state import AgentState
from agents.tools.metadata_filter import filter_documents_by_metadata, prioritize_documents_by_metadata
from llm.vector.hybrid_search import get_bm25_retriever


def keyword_retrieval_agent(state: AgentState) -> Dict[str, Any]:
    """
    Retrieves documents from ElasticSearch BM25 (sparse keyword store) and applies metadata filters and prioritization.
    """
    try:
        question = state.transformed_query
        filters = state.metadata_filters
        priorities = state.priorities

        bm25_retriever = get_bm25_retriever()

        # Perform initial retrieval from BM25
        retrieved_docs = bm25_retriever.invoke(question)

        # Apply metadata filtering
        filtered_docs = filter_documents_by_metadata(retrieved_docs, filters)

        # Apply metadata prioritization
        prioritized_docs = prioritize_documents_by_metadata(filtered_docs, priorities)

        # Add a specific tag to the documents for easier identification in streaming
        for doc in prioritized_docs:
            doc.metadata["stream_tag"] = "keyword_retrieved_docs"

        return {"documents": prioritized_docs}
    except Exception as e:
        return {"error": str(e)}
