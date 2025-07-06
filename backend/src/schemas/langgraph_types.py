"""
Enhanced LangGraph and LangChain Type Definitions
Provides strongly typed interfaces using native LangChain/LangGraph types.
"""

from typing import Any, Dict, List, Optional, Protocol, TypedDict, Union

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langgraph.graph import CompiledGraph, StateGraph
from pydantic import BaseModel, Field


# LangGraph State Types
class GraphState(TypedDict, total=False):
    """
    Enhanced state type using LangGraph's TypedDict pattern.
    Provides better type safety for graph operations.
    """

    # Core conversation
    messages: List[BaseMessage]
    user_query: str

    # User and session management
    user_id: str
    session_id: Optional[str]
    thread_id: Optional[str]

    # Processing state
    supervisor_decision: Optional[str]
    query_complexity: Optional[float]
    contextualized_query: Optional[str]

    # Memory and context
    memory_summary: Optional[str]
    relevant_memories: Optional[List[Dict[str, Any]]]

    # Retrieval results
    retrieved_docs: Optional[str]
    all_retrieved_docs: Optional[List[Document]]

    # Final outputs
    final_answer: Optional[str]
    error: Optional[str]
    retry_count: int


# LangChain Runnable Types
class AgentRunnable(Runnable[GraphState, GraphState], Protocol):
    """Protocol for agent runnables that process GraphState."""

    def invoke(self, input: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
        """Process the state and return updated state."""
        ...

    async def ainvoke(self, input: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
        """Async version of invoke."""
        ...


class RetrieverRunnable(Runnable[str, List[Document]], Protocol):
    """Protocol for retriever runnables."""

    def invoke(self, input: str, config: Optional[RunnableConfig] = None) -> List[Document]:
        """Retrieve documents for a query."""
        ...


# Enhanced Agent Protocols using LangChain types
class LangChainComplexityAnalyzer(Protocol):
    """Complexity analyzer using LangChain Runnable interface."""

    def as_runnable(self) -> Runnable[Dict[str, Any], Dict[str, Any]]:
        """Return as LangChain Runnable."""
        ...


class LangChainContextualizer(Protocol):
    """Contextualizer using LangChain Runnable interface."""

    def as_runnable(self) -> AgentRunnable:
        """Return as LangChain Runnable."""
        ...


class LangChainRetriever(Protocol):
    """Enhanced retriever protocol using LangChain types."""

    def get_base_retriever(self) -> BaseRetriever:
        """Get the underlying LangChain retriever."""
        ...

    def as_runnable(self) -> RetrieverRunnable:
        """Return as LangChain Runnable."""
        ...


class LangChainGenerator(Protocol):
    """Generator using LangChain Runnable interface."""

    def as_runnable(self) -> Runnable[GraphState, str]:
        """Return as LangChain Runnable."""
        ...


# Graph Construction Types
class NodeFunction(Protocol):
    """Protocol for LangGraph node functions."""

    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Process state and return updates."""
        ...


class ConditionalEdgeFunction(Protocol):
    """Protocol for LangGraph conditional edge functions."""

    def __call__(self, state: GraphState) -> str:
        """Determine next node based on state."""
        ...


# Enhanced Graph Builder
class TypedStateGraph:
    """
    Wrapper around LangGraph's StateGraph with enhanced typing.
    """

    def __init__(self, state_schema: type[GraphState]):
        self._graph = StateGraph(state_schema)
        self._state_schema = state_schema

    def add_node(self, name: str, action: NodeFunction) -> "TypedStateGraph":
        """Add a typed node to the graph."""
        self._graph.add_node(name, action)
        return self

    def add_conditional_edges(self, source: str, path: ConditionalEdgeFunction, path_map: Dict[str, str]) -> "TypedStateGraph":
        """Add conditional edges with typing."""
        self._graph.add_conditional_edges(source, path, path_map)
        return self

    def add_edge(self, source: str, target: str) -> "TypedStateGraph":
        """Add a simple edge."""
        self._graph.add_edge(source, target)
        return self

    def set_entry_point(self, node: str) -> "TypedStateGraph":
        """Set the entry point."""
        self._graph.set_entry_point(node)
        return self

    def compile(self, **kwargs) -> CompiledGraph:
        """Compile the graph."""
        return self._graph.compile(**kwargs)


# Pydantic Models for LangChain Integration
class LangChainDocument(BaseModel):
    """Enhanced document model compatible with LangChain Document."""

    page_content: str = Field(description="The content of the document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")

    def to_langchain_document(self) -> Document:
        """Convert to LangChain Document."""
        return Document(page_content=self.page_content, metadata=self.metadata)

    @classmethod
    def from_langchain_document(cls, doc: Document) -> "LangChainDocument":
        """Create from LangChain Document."""
        return cls(page_content=doc.page_content, metadata=doc.metadata)


class LangChainMessage(BaseModel):
    """Enhanced message model compatible with LangChain BaseMessage."""

    content: str = Field(description="Message content")
    role: str = Field(description="Message role (human, ai, system)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")

    def to_langchain_message(self) -> BaseMessage:
        """Convert to appropriate LangChain message type."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        if self.role == "human":
            return HumanMessage(content=self.content, **self.metadata)
        elif self.role == "ai":
            return AIMessage(content=self.content, **self.metadata)
        elif self.role == "system":
            return SystemMessage(content=self.content, **self.metadata)
        else:
            return HumanMessage(content=self.content, **self.metadata)


# Utility Types for Better Integration
RetrieverType = Union[BaseRetriever, RetrieverRunnable]
RunnableType = Union[Runnable[Input, Output], AgentRunnable]
GraphType = Union[StateGraph, TypedStateGraph, CompiledGraph]

# Type aliases for common patterns
MessageList = List[BaseMessage]
DocumentList = List[Document]
StateUpdate = Dict[str, Any]
