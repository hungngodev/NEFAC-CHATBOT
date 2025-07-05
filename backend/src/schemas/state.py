"""
Unified State Management for Hierarchical Multi-Agent System
Clean state definition without legacy compatibility layers.
"""

from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from typing_extensions import Annotated


class AgentState(BaseModel):
    """
    Unified state for the hierarchical multi-agent system.
    This is the single source of truth that flows through all nodes.
    """

    # Core conversation fields
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list, description="Conversation history with automatic message accumulation")
    user_query: str = Field(description="Current user query")

    # User and session management
    user_id: str = Field(default="default_user", description="User identifier for isolation")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    thread_id: Optional[str] = Field(default=None, description="Thread identifier for memory")

    # Supervisor and routing
    supervisor_decision: Optional[str] = Field(default=None, description="Routing decision from supervisor")
    query_complexity: Optional[float] = Field(default=None, description="Complexity score (0.0-1.0)")

    # Contextualizer
    contextualized_query: Optional[str] = Field(default=None, description="Standalone query with context")

    # Memory integration
    memory_summary: Optional[str] = Field(default=None, description="Relevant past interactions")
    relevant_memories: Optional[List[Dict[str, Any]]] = Field(default=None, description="Retrieved memories")

    # Retrieval
    retrieval_selection: Optional[Dict[str, Union[List[str], List[float]]]] = Field(default=None, description="Selected retrieval methods and weights")
    retrieved_docs: Optional[str] = Field(default=None, description="Retrieved documents as string")
    all_retrieved_docs: Optional[List[Any]] = Field(default=None, description="All retrieved documents")

    # ReAct worker
    react_steps: Optional[List[BaseMessage]] = Field(default=None, description="ReAct reasoning steps")
    react_iterations: int = Field(default=0, description="Number of ReAct iterations")

    # Final answer
    final_answer: Optional[str] = Field(default=None, description="Generated final answer")

    # Error handling
    error: Optional[str] = Field(default=None, description="Error message if any")

    # Retry mechanism
    retry_count: int = Field(default=0, description="Number of retries attempted")

    class Config:
        arbitrary_types_allowed = True


# Type alias for backward compatibility during transition
EnhancedAgentState = AgentState


def create_initial_state(user_query: str, user_id: str = "default_user", session_id: Optional[str] = None, thread_id: Optional[str] = None, **kwargs) -> AgentState:
    """Create initial state for a new query."""
    return AgentState(user_query=user_query, user_id=user_id, session_id=session_id, thread_id=thread_id, **kwargs)
