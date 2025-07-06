"""
Agent Protocol Definitions
Provides strongly typed interfaces for all agents using Protocol classes.
Enhanced with LangChain/LangGraph native types.
"""

from typing import Any, List, Optional, Protocol, runtime_checkable

from langchain_core.messages import BaseMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

# from langgraph.graph import CompiledGraph  # Removed to avoid import issues
from src.schemas.core_types import AgentState, GenerationResult, MemoryResult, QueryComplexityResult, QueryUnderstandingResult, ReActResult, RetrievalResult, ValidationResult
from src.schemas.langgraph_types import AgentRunnable, GraphState, RetrieverRunnable


@runtime_checkable
class ComplexityAnalyzerProtocol(Protocol):
    """Protocol for complexity analysis agents."""

    def analyze_complexity(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexityResult:
        """Analyze query complexity and return routing decision."""
        ...


@runtime_checkable
class ContextualizerProtocol(Protocol):
    """Protocol for query understanding and contextualization agents."""

    def process_query(self, state: AgentState, model: ChatOpenAI) -> QueryUnderstandingResult:
        """Process and contextualize user query."""
        ...


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for document retrieval agents."""

    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """Retrieve relevant documents based on query."""
        ...


@runtime_checkable
class ReActWorkerProtocol(Protocol):
    """Protocol for ReAct reasoning agents."""

    def reason_and_act(self, state: AgentState, model: ChatOpenAI, max_steps: int = 3) -> ReActResult:
        """Perform multi-step reasoning and action."""
        ...


@runtime_checkable
class GeneratorProtocol(Protocol):
    """Protocol for answer generation agents."""

    def generate_answer(self, state: AgentState, model: ChatOpenAI) -> GenerationResult:
        """Generate final answer from retrieved context."""
        ...


@runtime_checkable
class ValidatorProtocol(Protocol):
    """Protocol for answer validation agents."""

    def validate_answer(self, state: AgentState, model: ChatOpenAI) -> ValidationResult:
        """Validate generated answer against context."""
        ...


@runtime_checkable
class MemoryManagerProtocol(Protocol):
    """Protocol for memory management operations."""

    def store_interaction(self, user_id: str, query: str, response: str, session_id: Optional[str] = None, thread_id: Optional[str] = None) -> MemoryResult:
        """Store user interaction in memory."""
        ...

    def retrieve_memories(self, query: str, user_id: str, limit: int = 10) -> MemoryResult:
        """Retrieve relevant memories for context."""
        ...


# Service protocols for dependency injection
@runtime_checkable
class VectorStoreServiceProtocol(Protocol):
    """Protocol for vector store services."""

    def get_retriever(self):
        """Get vector store retriever."""
        ...

    def health_check(self) -> bool:
        """Check service health."""
        ...


@runtime_checkable
class KeywordSearchServiceProtocol(Protocol):
    """Protocol for keyword search services."""

    def get_retriever(self):
        """Get keyword search retriever."""
        ...

    def health_check(self) -> bool:
        """Check service health."""
        ...


@runtime_checkable
class GraphDatabaseServiceProtocol(Protocol):
    """Protocol for graph database services."""

    def execute_query(self, query: str):
        """Execute graph query."""
        ...

    def get_schema(self):
        """Get database schema."""
        ...

    def health_check(self) -> bool:
        """Check service health."""
        ...


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM services."""

    def get_model(self, model_name: Optional[str] = None) -> ChatOpenAI:
        """Get LLM model instance."""
        ...

    def get_fast_model(self) -> ChatOpenAI:
        """Get fast model for routing decisions."""
        ...

    def health_check(self) -> bool:
        """Check service health."""
        ...


# Enhanced protocols using LangChain/LangGraph types
@runtime_checkable
class RunnableComplexityAnalyzerProtocol(Protocol):
    """Protocol for complexity analysis agents using LangChain Runnable interface."""

    def analyze_complexity(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexityResult:
        """Analyze query complexity and return routing decision."""
        ...

    def as_runnable(self) -> Runnable[dict, dict]:
        """Return as LangChain Runnable for chain composition."""
        ...


@runtime_checkable
class RunnableContextualizerProtocol(Protocol):
    """Protocol for contextualizer agents using LangChain Runnable interface."""

    def process_query(self, state: AgentState, model: ChatOpenAI) -> QueryUnderstandingResult:
        """Process and contextualize user query."""
        ...

    def as_runnable(self) -> AgentRunnable:
        """Return as LangChain Runnable for chain composition."""
        ...


@runtime_checkable
class RunnableRetrieverProtocol(Protocol):
    """Protocol for retriever agents using LangChain Runnable interface."""

    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """Retrieve relevant documents based on query."""
        ...

    def get_base_retriever(self) -> BaseRetriever:
        """Get the underlying LangChain retriever."""
        ...

    def as_runnable(self) -> RetrieverRunnable:
        """Return as LangChain Runnable for chain composition."""
        ...


@runtime_checkable
class RunnableGeneratorProtocol(Protocol):
    """Protocol for generator agents using LangChain Runnable interface."""

    def generate_answer(self, state: AgentState, model: ChatOpenAI) -> GenerationResult:
        """Generate final answer from retrieved context."""
        ...

    def as_runnable(self) -> Runnable[GraphState, str]:
        """Return as LangChain Runnable for chain composition."""
        ...


# Composite protocol for full agent capabilities
@runtime_checkable
class MultiAgentSystemProtocol(Protocol):
    """Protocol for the complete multi-agent system."""

    complexity_analyzer: ComplexityAnalyzerProtocol
    contextualizer: ContextualizerProtocol
    retriever: RetrieverProtocol
    react_worker: ReActWorkerProtocol
    generator: GeneratorProtocol
    validator: ValidatorProtocol
    memory_manager: MemoryManagerProtocol

    def process_query(self, query: str, user_id: str, session_id: Optional[str] = None, thread_id: Optional[str] = None) -> GenerationResult:
        """Process a complete user query through the system."""
        ...


@runtime_checkable
class LangGraphSystemProtocol(Protocol):
    """Protocol for LangGraph-based multi-agent system."""

    def get_graph(self) -> Any:  # CompiledGraph
        """Get the compiled LangGraph."""
        ...

    def create_runnable_chain(self) -> Runnable[GraphState, GraphState]:
        """Create a runnable chain from the graph."""
        ...

    async def aprocess_query(self, query: str, user_id: str, config: Optional[RunnableConfig] = None) -> GenerationResult:
        """Async process query using LangGraph."""
        ...
