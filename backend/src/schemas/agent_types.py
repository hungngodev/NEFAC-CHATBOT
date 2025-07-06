"""
Strongly Typed Agent Result Types
Eliminates Any usage and provides consistent interfaces across all agents.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Generic, List, Optional, TypeVar, Union

from langchain_core.documents import Document
from pydantic import Field

# Base generic type for agent results
T = TypeVar("T")


@dataclass
class AgentResult(Generic[T]):
    """
    Strongly typed result container for all agents.
    Eliminates Dict[str, Any] usage throughout the system.
    """

    data: T
    success: bool = True
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)  # String keys and values only

    @property
    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.success and self.error is None

    @property
    def is_failure(self) -> bool:
        """Check if the operation failed."""
        return not self.success or self.error is not None


# Enums for better type safety
class ComplexityCategory(str, Enum):
    """Query complexity categories."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class RecommendedRoute(str, Enum):
    """Recommended processing routes."""

    RETRIEVER = "route_to_retriever"
    REACT = "route_to_react"
    FALLBACK = "route_to_fallback"


class QueryIntent(str, Enum):
    """Query intent classifications."""

    DOCUMENT_REQUEST = "document_request"
    STRUCTURED_GRAPH_QUERY = "structured_graph_query"
    STATISTICAL_GRAPH_QUERY = "statistical_graph_query"
    GENERAL_QUERY = "general_query"
    COMPARISON_QUERY = "comparison_query"
    ANALYSIS_QUERY = "analysis_query"


class RetrievalMethod(str, Enum):
    """Available retrieval methods."""

    DENSE = "dense"
    SPARSE = "sparse"
    GRAPH = "graph"
    HYBRID = "hybrid"


# Agent-specific data types
@dataclass
class QueryComplexityData:
    """Data returned by complexity analysis."""

    complexity_score: float = Field(ge=0.0, le=1.0, description="Overall complexity score")
    reasoning_required: bool = Field(description="Whether multi-step reasoning is needed")
    multi_hop_needed: bool = Field(description="Whether multiple retrieval steps are required")
    tool_usage_required: bool = Field(description="Whether tools are needed")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in assessment")

    # Detailed breakdown
    linguistic_complexity: float = Field(ge=0.0, le=1.0, description="Language complexity")
    domain_complexity: float = Field(ge=0.0, le=1.0, description="Legal domain complexity")
    reasoning_complexity: float = Field(ge=0.0, le=1.0, description="Reasoning requirements")
    temporal_complexity: float = Field(ge=0.0, le=1.0, description="Time-based complexity")

    # Classifications
    complexity_category: ComplexityCategory = Field(description="Complexity category")
    recommended_route: RecommendedRoute = Field(description="Recommended processing route")
    reasoning: str = Field(description="Explanation of complexity assessment")


@dataclass
class QueryUnderstandingData:
    """Data returned by query understanding."""

    contextualized_query: str = Field(description="Standalone query with context")
    intent: QueryIntent = Field(description="Classified query intent")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    structured_query: Optional[str] = Field(default=None, description="Generated Cypher query")
    statistical_query: Optional[str] = Field(default=None, description="Statistical query")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="Processing confidence")


@dataclass
class DocumentMetadata:
    """Structured document metadata."""

    source: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    page_number: Optional[int] = None
    document_id: Optional[str] = None
    relevance_score: Optional[float] = None
    stream_tag: Optional[str] = None


@dataclass
class RetrievalData:
    """Data returned by retrieval operations."""

    documents: List[Document] = field(default_factory=list)
    retrieval_methods_used: List[RetrievalMethod] = field(default_factory=list)
    total_documents_found: int = 0
    documents_after_deduplication: int = 0
    deduplication_applied: bool = False
    reranking_applied: bool = False
    query_expansion_applied: bool = False
    retrieval_time_ms: Optional[float] = None


@dataclass
class ReasoningStep:
    """Individual reasoning step in ReAct process."""

    step_number: int
    thought: str
    action: str
    observation: str
    sub_question: Optional[str] = None
    documents_retrieved: int = 0


@dataclass
class ReActData:
    """Data returned by ReAct reasoning."""

    final_answer: str = Field(description="Generated final answer")
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    documents_used: List[Document] = field(default_factory=list)
    iterations_completed: int = 0
    max_iterations: int = 3
    sub_questions_generated: List[str] = field(default_factory=list)
    total_reasoning_time_ms: Optional[float] = None
    convergence_achieved: bool = False


@dataclass
class GenerationData:
    """Data returned by answer generation."""

    answer: str = Field(description="Generated answer")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Generation confidence")
    sources_cited: List[str] = field(default_factory=list)
    word_count: int = 0
    generation_time_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    model_used: Optional[str] = None


@dataclass
class ValidationData:
    """Data returned by validation."""

    is_valid: bool = Field(description="Whether answer is valid")
    confidence: float = Field(ge=0.0, le=1.0, description="Validation confidence")
    reason: str = Field(description="Validation reasoning")
    issues_found: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class MemoryData:
    """Data returned by memory operations."""

    memories_retrieved: List[Dict[str, str]] = field(default_factory=list)
    memory_summary: str = ""
    relevance_scores: List[float] = field(default_factory=list)
    storage_successful: bool = False
    retrieval_time_ms: Optional[float] = None


# Specific result types for each agent
QueryComplexityResult = AgentResult[QueryComplexityData]
QueryUnderstandingResult = AgentResult[QueryUnderstandingData]
RetrievalResult = AgentResult[RetrievalData]
ReActResult = AgentResult[ReActData]
GenerationResult = AgentResult[GenerationData]
ValidationResult = AgentResult[ValidationData]
MemoryResult = AgentResult[MemoryData]


# Union type for any agent result
AnyAgentResult = Union[QueryComplexityResult, QueryUnderstandingResult, RetrievalResult, ReActResult, GenerationResult, ValidationResult, MemoryResult]


# Helper functions for creating results
def create_success_result(data: T, execution_time_ms: Optional[float] = None, **metadata) -> AgentResult[T]:
    """Create a successful agent result."""
    return AgentResult(data=data, success=True, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


def create_error_result(error: str, execution_time_ms: Optional[float] = None, **metadata) -> AgentResult[None]:
    """Create a failed agent result."""
    return AgentResult(data=None, success=False, error=error, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


# Type aliases for the current system
ModernAgentReturn = AnyAgentResult  # Standard agent return type
