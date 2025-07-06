"""
Enhanced Retrieval Worker - Unified Implementation
This module now imports from the enhanced retrieval_tools.py for consistency.
All functionality has been merged into retrieval_tools.py for better maintainability.
"""

import logging
from typing import List

from langchain_core.documents import Document

from src.core.agents.tools.retrieval.retrieval_tools import RetrievalAgent as EnhancedRetrievalAgent
from src.schemas.state import AgentState

logger = logging.getLogger(__name__)


# Use the enhanced implementation directly
RetrievalAgent = EnhancedRetrievalAgent

# Create global instance
_retrieval_agent = RetrievalAgent()


def retrieval_agent(state: AgentState) -> List[Document]:
    """
    Main interface function - uses the enhanced implementation.
    Returns documents directly for compatibility with existing code.
    """
    result = _retrieval_agent.retrieve_documents(state)

    if result.is_success:
        return result.data.documents
    else:
        logger.error(f"Retrieval failed: {result.error}")
        return []


# Export classes for direct use
__all__ = ["RetrievalAgent", "retrieval_agent"]
