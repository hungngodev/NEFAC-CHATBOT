from typing import Any, Dict

from agents.state import AgentState
from agents.tools.metadata_filter import filter_documents_by_metadata, prioritize_documents_by_metadata
from llm.vector.hybrid_search import get_qdrant_retriever


def vector_retrieval_agent(state: AgentState) -> Dict[str, Any]:
    """
    Retrieves documents from Qdrant (dense vector store) and applies metadata filters and prioritization.
    """
    try:
        question = state.transformed_query
        filters = state.metadata_filters
        priorities = state.priorities

        qdrant_retriever = get_qdrant_retriever()

        # Perform initial retrieval from Qdrant
        retrieved_docs = qdrant_retriever.invoke(question)

        # Apply metadata filtering
        filtered_docs = filter_documents_by_metadata(retrieved_docs, filters)

        # Apply metadata prioritization
        prioritized_docs = prioritize_documents_by_metadata(filtered_docs, priorities)

        # Add a specific tag to the documents for easier identification in streaming
        for doc in prioritized_docs:
            doc.metadata["stream_tag"] = "vector_retrieved_docs"

        return {"documents": prioritized_docs}
    except Exception as e:
        return {"error": str(e)}
