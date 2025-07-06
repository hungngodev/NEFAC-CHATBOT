"""
Retriever Worker - Enhanced with Unified Retrieval System
Provides a worker interface for the unified retrieval system with comprehensive metadata.
"""

from typing import List, Optional, TypedDict

from langchain_core.documents import Document

from src.core.agents.tools.retrieval.retrieval_tools import RetrievalAgent
from src.schemas.core_types import AgentState, RetrievalMetadata


class RetrieverWorkerOutput(TypedDict):
    documents: List[Document]
    retrieval_metadata: RetrievalMetadata
    success: bool
    error: Optional[str]


def retriever_worker(state: AgentState) -> RetrieverWorkerOutput:
    """
    Enhanced worker that retrieves documents using the unified retrieval system.
    Returns comprehensive metadata about the retrieval process.
    """
    try:
        agent = RetrievalAgent()
        result = agent.retrieve_documents(state)

        if result.is_success:
            return {
                "documents": result.data.documents,
                "retrieval_metadata": {
                    "methods_used": [m.value for m in result.data.retrieval_methods_used],
                    "total_documents_found": result.data.total_documents_found,
                    "documents_after_deduplication": result.data.documents_after_deduplication,
                    "deduplication_applied": result.data.deduplication_applied,
                    "reranking_applied": result.data.reranking_applied,
                    "query_expansion_applied": result.data.query_expansion_applied,
                    "retrieval_time_ms": result.data.retrieval_time_ms,
                },
                "success": True,
                "error": None,
            }
        else:
            return {"documents": [], "retrieval_metadata": {}, "success": False, "error": result.error}

    except Exception as e:
        return {"documents": [], "retrieval_metadata": {}, "success": False, "error": f"Retriever worker error: {str(e)}"}
