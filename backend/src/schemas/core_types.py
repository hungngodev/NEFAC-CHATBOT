"""
Centralized Type Definitions for NEFAC Multi-Agent System
This file consolidates all type definitions from across the codebase into a single location.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Protocol, TypedDict, TypeVar, Union

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

# === Generic Types ===
T = TypeVar("T")

# === Core Enums ===


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""

    VALIDATION = "validation"
    PROCESSING = "processing"
    EXTERNAL_SERVICE = "external_service"
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    RESOURCE = "resource"


class ComplexityCategory(str, Enum):
    """Query complexity categories."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class RecommendedRoute(str, Enum):
    """Recommended processing routes."""

    DIRECT = "direct"
    RETRIEVAL = "retrieval"
    REACT = "react"
    COMPLEX_REASONING = "complex_reasoning"


class QueryIntent(str, Enum):
    """Query intent categories."""

    DOCUMENT_REQUEST = "document_request"
    GENERAL = "general"
    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"


class RetrievalMethod(str, Enum):
    """Available retrieval methods."""

    DENSE = "dense"
    SPARSE = "sparse"
    GRAPH = "graph"
    HYBRID = "hybrid"


# === Core Data Classes ===


@dataclass
class AgentResult(Generic[T]):
    """Strongly typed result container for all agents."""

    data: T
    success: bool = True
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.success and self.error is None

    @property
    def is_failure(self) -> bool:
        """Check if the operation failed."""
        return not self.success or self.error is not None


@dataclass
class ComplexityMetrics:
    """Detailed complexity metrics for analysis."""

    linguistic_score: float
    domain_score: float
    reasoning_score: float
    temporal_score: float
    multi_hop_score: float
    confidence: float


@dataclass
class QueryComplexityData:
    """Data returned by complexity analysis."""

    complexity_score: float
    category: ComplexityCategory
    recommended_route: RecommendedRoute
    reasoning_required: bool
    multi_hop_needed: bool
    confidence: float
    reasoning: str
    metrics: Optional[ComplexityMetrics] = None


@dataclass
class QueryUnderstandingData:
    """Data returned by query understanding."""

    contextualized_query: str
    intent: QueryIntent
    entities: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class DocumentMetadata:
    """Metadata for retrieved documents."""

    source: str
    retrieval_method: str
    retrieval_rank: int
    confidence_score: Optional[float] = None
    stream_tag: str = "retrieved_docs"


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
    confidence: float = 0.0


@dataclass
class ReActData:
    """Data returned by ReAct reasoning."""

    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    total_steps: int = 0
    reasoning_time_ms: Optional[float] = None
    tools_used: List[str] = field(default_factory=list)


@dataclass
class GenerationData:
    """Data returned by answer generation."""

    answer: str
    confidence: float = 0.0
    sources_used: List[str] = field(default_factory=list)
    generation_time_ms: Optional[float] = None
    token_count: Optional[int] = None


@dataclass
class ValidationData:
    """Data returned by validation."""

    is_valid: bool
    confidence: float = 0.0
    reason: str = ""
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


@dataclass
class MemoryEntry:
    """Structured memory entry with metadata."""

    id: str
    user_id: str
    session_id: str
    query: str
    response: str
    timestamp: datetime
    metadata: Dict[str, Union[str, int, float, bool]]
    embedding: Optional[List[float]] = None
    relevance_score: Optional[float] = None


@dataclass
class MemorySearchResult:
    """Result from memory search operations."""

    entries: List[MemoryEntry]
    total_found: int
    search_time_ms: float
    query_embedding: Optional[List[float]] = None


@dataclass
class ExtractedInformation:
    """Structured information extracted from documents."""

    title: Optional[str] = None
    source_url: Optional[str] = None
    page_content_snippet: str = ""
    entities: List[str] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    extraction_method: str = "basic"
    metadata: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)


@dataclass
class DocumentCitation:
    """Citation information for documents."""

    document_id: str
    title: str
    source_url: str
    page_content_snippet: str
    relevance_score: float = 0.0
    citation_text: str = ""
    metadata: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)


@dataclass
class SessionMemoryEntry:
    """Session-specific memory entry."""

    query: str
    response: str
    timestamp: datetime
    relevance_score: float = 0.0
    metadata: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)


@dataclass
class RetrievalMetadata:
    """Structured retrieval metadata."""

    methods_used: List[str] = field(default_factory=list)
    total_found: int = 0
    deduplication_applied: bool = False
    reranking_applied: bool = False
    execution_time_ms: float = 0.0
    query_expansion_applied: bool = False


@dataclass
class SearchFilter:
    """Structured search filter."""

    source_types: Optional[List[str]] = None
    date_range: Optional[tuple[str, str]] = None
    categories: Optional[List[str]] = None
    metadata_filters: Optional[Dict[str, Union[str, int, float, bool]]] = None


# === Result Type Aliases ===
QueryComplexityResult = AgentResult[QueryComplexityData]
QueryUnderstandingResult = AgentResult[QueryUnderstandingData]
RetrievalResult = AgentResult[RetrievalData]
ReActResult = AgentResult[ReActData]
GenerationResult = AgentResult[GenerationData]
ValidationResult = AgentResult[ValidationData]
MemoryResult = AgentResult[MemoryData]

AnyAgentResult = Union[QueryComplexityResult, QueryUnderstandingResult, RetrievalResult, ReActResult, GenerationResult, ValidationResult, MemoryResult]

# === TypedDict Definitions ===


class RetrieverWorkerOutput(TypedDict):
    """Output from retriever worker."""

    retrieved_docs: str
    retriever_query: str
    all_retrieved_docs: List[Document]
    retrieval_metadata: RetrievalMetadata
    error: Optional[str]


class ReactAgentRetrievalOutput(TypedDict):
    """Output from ReAct agent retrieval."""

    documents: List[Document]
    retrieval_metadata: RetrievalMetadata
    error: Optional[str]


class InformationExtractionOutput(TypedDict):
    """Output from information extraction."""

    extracted_info: Optional[List[ExtractedInformation]]
    documents: List[Document]
    error: Optional[str]


class ContextSummarizationOutput(TypedDict):
    """Output from context summarization."""

    summarized_content: List[Document]
    documents: List[Document]
    error: Optional[str]


class CitationAttributionOutput(TypedDict):
    """Output from citation attribution."""

    citations: List[DocumentCitation]
    documents: List[Document]
    error: Optional[str]


class ContextProcessorOutput(TypedDict):
    """Output from context processing."""

    processed_context: str
    citations: List[DocumentCitation]
    extracted_info: List[ExtractedInformation]
    documents: List[Document]
    error: Optional[str]


# === Protocol Definitions ===


class ComplexityAnalyzerProtocol(Protocol):
    """Protocol for complexity analysis agents."""

    def analyze_complexity(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexityResult:
        """Analyze query complexity and return routing decision."""
        ...


class ContextualizerProtocol(Protocol):
    """Protocol for query understanding and contextualization agents."""

    def process_query(self, state: Any, model: Any) -> QueryUnderstandingResult:  # AgentState
        """Process and contextualize user query."""
        ...


class RetrieverProtocol(Protocol):
    """Protocol for document retrieval agents."""

    def retrieve_documents(self, state: Any) -> RetrievalResult:  # AgentState
        """Retrieve relevant documents based on query."""
        ...


class ReActWorkerProtocol(Protocol):
    """Protocol for ReAct reasoning agents."""

    def reason_and_act(self, state: Any, tools: List[Any]) -> ReActResult:  # AgentState
        """Perform multi-step reasoning with tool usage."""
        ...


class GeneratorProtocol(Protocol):
    """Protocol for answer generation agents."""

    def generate_answer(self, state: Any, model: Any) -> GenerationResult:  # AgentState
        """Generate final answer from retrieved context."""
        ...


class ValidatorProtocol(Protocol):
    """Protocol for answer validation agents."""

    def validate_answer(self, state: Any, model: Any) -> ValidationResult:  # AgentState
        """Validate generated answer against context."""
        ...


class MemoryManagerProtocol(Protocol):
    """Protocol for memory management agents."""

    def store_memory(self, user_id: str, session_id: str, query: str, response: str) -> MemoryResult:
        """Store interaction in memory."""
        ...

    def retrieve_memory(self, user_id: str, query: str, limit: int = 5) -> MemoryResult:
        """Retrieve relevant memories."""
        ...


class VectorStoreServiceProtocol(Protocol):
    """Protocol for vector store services."""

    def similarity_search(self, query: str, k: int = 10, filter: Optional[SearchFilter] = None) -> List[Document]:
        """Perform similarity search."""
        ...


class KeywordSearchServiceProtocol(Protocol):
    """Protocol for keyword search services."""

    def search(self, query: str, k: int = 10, filter: Optional[SearchFilter] = None) -> List[Document]:
        """Perform keyword search."""
        ...


class GraphDatabaseServiceProtocol(Protocol):
    """Protocol for graph database services."""

    def query_graph(self, query: str, entities: Optional[List[str]] = None) -> List[Document]:
        """Query knowledge graph."""
        ...


class LLMServiceProtocol(Protocol):
    """Protocol for LLM services."""

    def generate(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.0) -> str:
        """Generate text using LLM."""
        ...


# === Factory Functions ===


def create_success_result(data: T, execution_time_ms: Optional[float] = None, **metadata) -> AgentResult[T]:
    """Create a successful agent result."""
    return AgentResult(data=data, success=True, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


def create_error_result(error: str, execution_time_ms: Optional[float] = None, **metadata) -> AgentResult[None]:
    """Create a failed agent result."""
    return AgentResult(data=None, success=False, error=error, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


def create_extracted_info(
    title: Optional[str] = None, source_url: Optional[str] = None, page_content_snippet: str = "", entities: Optional[List[str]] = None, key_facts: Optional[List[str]] = None, topics: Optional[List[str]] = None, confidence_score: Optional[float] = None, extraction_method: str = "basic", **metadata
) -> ExtractedInformation:
    """Factory function to create ExtractedInformation."""
    return ExtractedInformation(title=title, source_url=source_url, page_content_snippet=page_content_snippet, entities=entities or [], key_facts=key_facts or [], topics=topics or [], confidence_score=confidence_score, extraction_method=extraction_method, metadata=metadata)


def create_citation(document_id: str, title: str, source_url: str, page_content_snippet: str, relevance_score: float = 0.0, citation_text: str = "", **metadata) -> DocumentCitation:
    """Factory function to create DocumentCitation."""
    return DocumentCitation(document_id=document_id, title=title, source_url=source_url, page_content_snippet=page_content_snippet, relevance_score=relevance_score, citation_text=citation_text, metadata=metadata)


def create_memory_entry(query: str, response: str, timestamp: Optional[datetime] = None, relevance_score: float = 0.0, **metadata) -> SessionMemoryEntry:
    """Factory function to create SessionMemoryEntry."""
    return SessionMemoryEntry(query=query, response=response, timestamp=timestamp or datetime.now(), relevance_score=relevance_score, metadata=metadata)


# === Type Aliases for Backward Compatibility ===
ModernAgentReturn = AnyAgentResult
