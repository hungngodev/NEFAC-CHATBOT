"""
Hierarchical Multi-Agent System
Top-down architecture with clean separation of concerns.
"""

# Top-level imports for the hierarchical agent system
from backend.src.core.agents.supervisor.complexity_analyzer import ComplexityAnalyzer, QueryComplexity
from backend.src.core.agents.tools.retrieval.retrieval_tools import create_retrieval_tool, create_retriever_worker_function
from backend.src.core.agents.workers.react.react_worker import create_react_agent_function
from backend.src.core.agents.workers.retriever.retrieval import retrieval_agent
from backend.src.schemas.core_types import AgentState, create_initial_state

__all__ = [
    # Core state management
    "AgentState",
    "create_initial_state",
    # Supervisor layer
    "ComplexityAnalyzer",
    "QueryComplexity",
    # Worker layer
    "create_react_agent_function",
    "retrieval_agent",
    # Tool layer
    "create_retrieval_tool",
    "create_retriever_worker_function",
]
