from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Generic, Literal, TypedDict, TypeVar

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage, BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from backend.src.schemas.langgraph_types import LangChainDocument


class AgentState(MessagesState):
    """
    Unified state for the hierarchical multi-agent system.
    This is the single source of truth that flows through all nodes.
    """

    summarized_messages: list[AnyMessage]

    # Core conversation fields
    user_query: str = Field(description="Current user query")

    # User and session management
    user_id: str = Field(default="default_user", description="User identifier for isolation")
    session_id: str | None = Field(default=None, description="Session identifier")
    thread_id: str | None = Field(default=None, description="Thread identifier for memory")

    # Contextualizer
    contextualized_query: str | None = Field(default=None, description="Standalone query with context")

    # Retrieval
    retrieval_selection: dict[str, list[str] | list[float]] | None = Field(default=None, description="Selected retrieval methods and weights")
    retrieved_docs: str | None = Field(default=None, description="Retrieved documents as string")
    all_retrieved_docs: list[Document] | None = Field(default=None, description="All retrieved documents")

    # ReAct worker
    react_steps: list[BaseMessage] | None = Field(default=None, description="ReAct reasoning steps")
    react_iterations: int = Field(default=0, description="Number of ReAct iterations")

    # Final answer
    final_answer: str | None = Field(default=None, description="Generated final answer")

    # Error handling
    error: str | None = Field(default=None, description="Error message if any")

    # Retry mechanism
    retry_count: int = Field(default=0, description="Number of retries attempted")


class BaseMetadata(BaseModel):

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="allow")
    id: int | str = Field(description="Unique identifier for the document")
    title: str = Field(min_length=1, description="Document title")
    filename: str = Field(min_length=1, description="Original filename")
    source_url: str = Field(description="Source URL of the document")
    date: str = Field(description="Document creation/publication date")
    modified: str | None = Field(default=None, description="Last modification date")
    mime_type: str | None = Field(default=None, description="MIME type of the document")
    file_size: int | None = Field(default=None, ge=0, description="File size in bytes")
    download_date: str | None = Field(default=None, description="Date when document was downloaded")
    crawler_version: str | None = Field(default=None, description="Version of crawler used")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("file://")):
            raise ValueError("source_url must be a valid URL")
        return v


class AuthorMetadata(BaseModel):

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Author's full name")
    slug: str = Field(min_length=1, description="URL-friendly author identifier")
    uri: str = Field(description="Author's URI/profile link")
    description: str | None = Field(default=None, description="Author biography or description")
    email: str | None = Field(default=None, description="Author's email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class CategoryMetadata(BaseModel):
    name: str
    slug: str
    description: str | None = None
    count: int | None = None


class ContentMetadata(BaseMetadata):
    graphql_id: str | None = None
    slug: str
    file_path: str
    uri: str
    link: str
    source_url: str
    excerpt: str | None = None
    content_length: int | None = None
    author: AuthorMetadata | None = None
    categories: list[CategoryMetadata] | None = None
    tags: list[str] | None = None
    featured_image: object | None = None
    comment_count: int | None = None
    source: str | None = None
    file_size: int | None = None
    mime_type: str | None = None


class PDFMetadata(BaseMetadata):
    alt_text: str | None = None
    description: str | None = None
    caption: str | None = None
    source: str | None = None
    file_created: str | None = None
    file_modified: str | None = None
    file_path: str
    processing_timestamp: float | None = None
    http_status_code: int | None = None
    http_headers: dict[str, object] | None = None
    content_length_header: str | None = None
    last_modified_header: str | None = None
    etag_header: str | None = None
    server_header: str | None = None
    content_encoding: str | None = None
    content_disposition: str | None = None
    cache_control: str | None = None
    expires: str | None = None
    file_extension: str | None = None
    file_type_category: str | None = None
    is_image: bool | None = None
    is_document: bool | None = None
    is_archive: bool | None = None
    validation_status: str | None = None


class YouTubeMetadata(BaseModel):
    id: str
    title: str
    video_id: str
    source_url: str
    date: str
    modified: str | None = None
    description: str | None = None
    duration: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    uploader: str | None = None
    channel: str | None = None
    channel_id: str | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    thumbnail: str | None = None
    uploader_url: str | None = None
    availability: str | None = None
    live_status: str | None = None
    release_timestamp: str | None = None
    chapters: dict[str, Any] | None = None
    heatmap: dict[str, Any] | None = None
    transcript_available: bool | None = None
    transcript_file: str | None = None
    transcript_length: int | None = None
    transcript_word_count: int | None = None
    mime_type: str | None = None
    source: str | None = None
    download_date: str | None = None
    crawler_version: str | None = None
    file_size: int | None = None


class PDFChunkMetadata(PDFMetadata):
    page_number: int = 0  # Optional, for compatibility
    total_pages: int
    chunk_index: int
    total_chunks_in_page: int = 0  # Optional, for compatibility
    total_chunks_in_document: int = 0  # For document-level chunking
    chunking_strategy: str
    pages: list[int] = field(default_factory=list)  # List of page numbers this chunk covers
    pages_info: list[dict[str, Any]] = field(default_factory=list)  # List of page info dicts for each page covered by the chunk


class ContentChunkMetadata(ContentMetadata):
    section_path: list[str]
    section_index: int
    chunk_index: int
    total_chunks_in_section: int
    chunking_strategy: str
    anchor: str | None = None
    html_url: str | None = None
    chunk_start: int | None = None
    chunk_end: int | None = None


class YouTubeChunkMetadata(YouTubeMetadata):
    chunk_index: int
    total_chunks_in_video: int
    chunking_strategy: str
    start_time: float = 0.0
    end_time: float = 0.0


class Entities(BaseModel):
    """Schema for entity extraction from text."""

    names: list[str] = Field(..., description="Canonical entity names (person, org, etc.) in the text.")
    types: list[str] | None = Field(None, description="Entity types (Person, Organization, etc.)")


class QueryContext(BaseModel):
    """Context information for query processing."""

    entities: list[dict[str, object]] = Field(default_factory=list, description="Extracted entities from query")
    metadata_filters: dict[str, object] = Field(default_factory=dict, description="Metadata filters to apply")
    priorities: list[str] = Field(default_factory=list, description="Priority ordering for results")
    structured_query: str | None = Field(None, description="Structured query for direct execution")
    statistical_query: str | None = Field(None, description="Statistical query for aggregations")


class DocumentMetadata(BaseModel):
    """Metadata for retrieved documents."""

    source: str = Field(description="Source of the document")
    retrieval_method: str = Field(description="Method used to retrieve this document")
    retrieval_rank: int = Field(description="Rank in retrieval results")
    stream_tag: str = Field(description="Tag for streaming identification")
    entity: str | None = Field(None, description="Associated entity if applicable")
    confidence_score: float | None = Field(None, description="Confidence score for relevance")


class APIResponse(BaseModel):
    """Base API response schema with consistent structure."""

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True, use_enum_values=True)

    success: bool = Field(description="Whether the request was successful")
    message: str = Field(description="Human-readable response message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class LoadingStatusResponse(BaseModel):
    """Enhanced loading status response with validation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    current: int = Field(ge=0, description="Current progress count")
    total: int = Field(gt=0, description="Total items to process")
    status: str = Field(description="Current status message")
    is_loading: bool = Field(description="Whether loading is in progress")

    @field_validator("current")
    @classmethod
    def current_not_exceed_total(cls, v: int, info: ValidationInfo) -> int:
        total = info.data.get("total")
        if total is not None and v > total:
            raise ValueError("Current cannot exceed total")
        return v


class Citation(BaseModel):
    """Enhanced citation with validation and metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: str = Field(min_length=1, description="Unique identifier for the citation")
    context: str = Field(min_length=1, description="The citation used to generate the search result")
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Relevance score (0-1)")
    source_type: Literal["document", "web", "database"] | None = Field(default=None, description="Type of source")


class SearchResult(BaseModel):
    """Enhanced search result with comprehensive metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    title: str = Field(min_length=1, description="The title of the search result")
    link: str = Field(description="The link to the source of search result")
    summary: str = Field(min_length=1, description="A brief summary of the search result and relevance to prompt")
    citations: list[Citation] = Field(description="A list of citations used to generate the search result")
    type: str | None = Field(default=None, description="Type of search result")
    timestamp_seconds: int | None = Field(default=None, ge=0, description="Timestamp in seconds")
    content: str | None = Field(default=None, description="Full content of the search result")
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0, description="Confidence score")

    @field_validator("link")
    @classmethod
    def validate_link(cls, v: str) -> str:
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("/")):
            raise ValueError("Link must be a valid URL or path")
        return v


class SearchResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    results: list[SearchResult] = Field(description="A list of search results")
    total_results: int = Field(ge=0, description="Total number of results found")
    query_time_ms: int | None = Field(default=None, ge=0, description="Query execution time in milliseconds")

    @field_validator("total_results")
    @classmethod
    def validate_total_results(cls, v: int, info: ValidationInfo) -> int:
        results = info.data.get("results")
        if results is not None and v != len(results):
            raise ValueError("total_results must match length of results list")
        return v


class BaseEvent(BaseModel):
    """Base event schema with common fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    order: int = Field(ge=0, description="Event order in sequence")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    event_id: str = Field(description="Unique event identifier")


class ContextEvent(BaseEvent):
    """Enhanced context event with validation."""

    context: list[SearchResult] = Field(description="List of contextual search results")
    context_type: Literal["retrieval", "memory", "external"] | None = Field(default="retrieval", description="Type of context")


class ReformulatedEvent(BaseEvent):
    """Enhanced reformulated query event."""

    reformulated: str = Field(min_length=1, description="Reformulated query text")
    original_query: str | None = Field(default=None, description="Original query for comparison")
    reformulation_method: str | None = Field(default=None, description="Method used for reformulation")


class MessageEvent(BaseEvent):
    """Enhanced message event with metadata."""

    message: str = Field(min_length=1, description="Message content")
    message_type: Literal["info", "warning", "error", "success"] | None = Field(default="info", description="Message type")
    source: str | None = Field(default=None, description="Source of the message")


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    method: Literal[
        "multiquery",
        "decompose",
        "stepback",
        "hyde",
        "ragfusion",
        "factual",
        "contextual",
        "default",
    ] = Field(description="The selected query construction method.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Confidence in method selection")
    fallback_method: str | None = Field(default="default", description="Fallback method if primary fails")


class RetrievalSelection(BaseModel):
    """Enhanced retrieval selection with validation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    methods: list[Literal["graph", "dense", "sparse"]] = Field(
        description=("Which retrieval methods to apply—any combination of:\n" "• graph  – Neo4j knowledge-graph retriever\n" "• dense  – Qdrant semantic vector retriever\n" "• sparse – Elasticsearch BM25 keyword retriever"),
    )
    weights: list[float] = Field(
        description=("A parallel list of weights for each method, summing to 1.0 if possible.\n" "If lengths mismatch or sum != 1, weights will be normalized equally."),
    )

    @field_validator("weights")
    def validate_weights(cls, v: list[float], info: ValidationInfo) -> list[float]:
        methods = info.data.get("methods")
        if methods is not None and len(v) != len(methods):
            raise ValueError("weights must have same length as methods")
        if all(w >= 0 for w in v) and sum(v) > 0:
            # Normalize weights to sum to 1.0
            total = sum(v)
            return [w / total for w in v]
        raise ValueError("weights must be positive and sum to > 0")


class MultiStepReasoning(BaseModel):
    """Enhanced multi-step reasoning with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    reasoning_steps: list[str] = Field(
        description="A list of reasoning steps to answer the user's query.",
    )
    step_types: list[str] | None = Field(default=None, description="Types of each reasoning step")
    confidence_scores: list[float] | None = Field(default=None, description="Confidence for each step")

    @classmethod
    @field_validator("step_types")
    def validate_step_types(cls, v: list[str] | None, info: "ValidationInfo") -> list[str] | None:
        reasoning_steps = info.data.get("reasoning_steps")
        if v is not None and reasoning_steps is not None and len(v) != len(reasoning_steps):
            raise ValueError("step_types must match length of reasoning_steps")


class Validation(BaseModel):

    is_valid: bool = Field(description="Whether the generated answer is valid or not.")
    reasoning: str = Field(min_length=1, description="The reasoning behind the validation.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the validation")
    validation_criteria: list[str] | None = Field(default=None, description="Criteria used for validation")
    suggestions: list[str] | None = Field(default=None, description="Suggestions for improvement if invalid")


# --- Query Complexity Schemas ---


# --- Strategy Selection Schemas ---


class StrategyRecommendation(BaseModel):
    """Recommended strategy based on complexity analysis."""

    primary_strategy: str = Field(description="Primary processing strategy to use")
    fallback_strategies: list[str] = Field(description="Alternative strategies if primary fails")
    reasoning: str = Field(description="Why this strategy was recommended")
    expected_accuracy: float = Field(description="Expected accuracy with this strategy (0-1)")
    resource_requirements: str = Field(description="Resource requirements: low, medium, high")


# --- Processing Metrics Schemas ---


class ProcessingMetrics(BaseModel):
    """Metrics for processing performance."""

    processing_time: float = Field(description="Time taken to process in seconds")
    tokens_used: int = Field(description="Number of tokens consumed")
    retrieval_count: int = Field(description="Number of retrieval operations")
    complexity_level: str = Field(description="Detected complexity level")
    strategy_used: str = Field(description="Strategy that was used")
    success: bool = Field(description="Whether processing was successful")
    error_message: str | None = Field(None, description="Error message if failed")


class ErrorResponse(APIResponse):
    """Error response schema with detailed error information."""

    success: bool = Field(default=False, description="Always false for error responses")
    error_code: str = Field(description="Machine-readable error code")
    details: dict[str, str | int | float | bool | list[str]] | None = Field(default=None, description="Additional error details")


T = TypeVar("T")


@dataclass
class DocumentCitation:
    """Structured citation information for documents."""

    title: str
    source_url: str
    page_number: str | None = None
    document_id: str = ""
    relevance_score: float | None = None
    citation_type: str = "document"  # document, webpage, pdf, etc.
    access_date: datetime | None = None
    page_content_snippet: str = ""
    authors: list[str] = field(default_factory=list)
    publication_date: datetime | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    citation_text: str = ""

    def to_dict(self) -> dict[str, str | int | float | bool | list[str] | None]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "source_url": self.source_url,
            "page_number": self.page_number,
            "document_id": self.document_id,
            "relevance_score": self.relevance_score,
            "citation_type": self.citation_type,
            "access_date": self.access_date.isoformat() if self.access_date else None,
            "authors": self.authors,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
        }


# Removed duplicate SessionMemoryEntry - using MemoryEntry instead


class DocumentCitationModel(BaseModel):
    """Pydantic model for document citations."""

    title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    page_number: str | None = None
    document_id: str = Field(default="")
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    citation_type: str = Field(default="document")
    access_date: datetime | None = None
    authors: list[str] = Field(default_factory=list)
    publication_date: datetime | None = None


class MemoryEntryModel(BaseModel):
    """Pydantic model for memory entries."""

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)
    embedding: list[float] | None = Field(default=None)
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)


# === Type Guards ===


def is_extracted_info(obj: Any) -> bool:
    """Type guard for ExtractedInformation."""
    return isinstance(obj, ExtractedInformation)


def is_citation(obj: Any) -> bool:
    """Type guard for DocumentCitation."""
    return isinstance(obj, DocumentCitation)


def is_memory_entry(obj: Any) -> bool:
    """Type guard for MemoryEntry."""
    return isinstance(obj, MemoryEntry)


# === Conversion Utilities ===


def dict_to_extracted_info(data: dict[str, Any]) -> ExtractedInformation:
    """Convert dictionary to ExtractedInformation."""
    return ExtractedInformation(
        title=data.get("title"),
        source_url=data.get("source_url"),
        page_content_snippet=data.get("page_content_snippet", ""),
        entities=data.get("entities", []),
        key_facts=data.get("key_facts", []),
        topics=data.get("topics", []),
        confidence_score=data.get("confidence_score"),
        extraction_method=data.get("extraction_method", "basic"),
        metadata=data.get("metadata", {}),
    )


def dict_to_citation(data: dict[str, Any]) -> DocumentCitation:
    """Convert dictionary to DocumentCitation."""
    return DocumentCitation(
        title=data["title"],
        source_url=data["source_url"],
        page_number=data.get("page_number"),
        document_id=data.get("document_id", ""),
        relevance_score=data.get("relevance_score"),
        citation_type=data.get("citation_type", "document"),
        access_date=datetime.fromisoformat(data["access_date"]) if data.get("access_date") else None,
        authors=data.get("authors", []),
        publication_date=datetime.fromisoformat(data["publication_date"]) if data.get("publication_date") else None,
    )


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
    error: str | None = None
    execution_time_ms: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)

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
class QueryUnderstandingData:
    """Data returned by query understanding."""

    contextualized_query: str
    intent: QueryIntent
    entities: list[str] = field(default_factory=list)
    key_concepts: list[str] = field(default_factory=list)
    confidence: float = 0.0


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

    reasoning_steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    total_steps: int = 0
    reasoning_time_ms: float | None = None
    tools_used: list[str] = field(default_factory=list)


@dataclass
class GenerationData:
    """Data returned by answer generation."""

    answer: str
    confidence: float = 0.0
    sources_used: list[str] = field(default_factory=list)
    generation_time_ms: float | None = None
    token_count: int | None = None


@dataclass
class ValidationData:
    """Data returned by validation."""

    is_valid: bool
    confidence: float = 0.0
    reason: str = ""
    issues_found: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class MemoryData:
    """Data returned by memory operations."""

    memories_retrieved: list[dict[str, str]] = field(default_factory=list)
    memory_summary: str = ""
    relevance_scores: list[float] = field(default_factory=list)
    storage_successful: bool = False
    retrieval_time_ms: float | None = None


@dataclass
class MemoryEntry:
    """Structured memory entry with metadata."""

    id: str
    user_id: str
    session_id: str
    query: str
    response: str
    timestamp: datetime
    metadata: dict[str, str | int | float | bool]
    embedding: list[float] | None = None
    relevance_score: float | None = None

    def to_document(self) -> Document:
        """Convert to LangChain Document for vector storage."""
        content = f"Query: {self.query}\nResponse: {self.response}"
        metadata = {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            **self.metadata,
        }
        return Document(page_content=content, metadata=metadata)


@dataclass
class MemorySearchResult:
    """Result from memory search operations."""

    entries: list[MemoryEntry]
    total_found: int
    search_time_ms: float
    query_embedding: list[float] | None = None


@dataclass
class ExtractedInformation:
    """Structured information extracted from documents."""

    title: str | None = None
    source_url: str | None = None
    page_content_snippet: str = ""
    entities: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    confidence_score: float | None = None
    extraction_method: str = "basic"
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass
class RetrievalMetadata:
    """Structured retrieval metadata."""

    methods_used: list[str] = field(default_factory=list)
    total_found: int = 0
    deduplication_applied: bool = False
    reranking_applied: bool = False
    execution_time_ms: float = 0.0
    query_expansion_applied: bool = False


@dataclass
class SearchFilter:
    """Structured search filter."""

    source_types: list[str] | None = None
    date_range: tuple[str, str] | None = None
    categories: list[str] | None = None
    metadata_filters: dict[str, str | int | float | bool] | None = None


# === Result Type Aliases ===
ReActResult = AgentResult[ReActData]
GenerationResult = AgentResult[GenerationData]
ValidationResult = AgentResult[ValidationData]
MemoryResult = AgentResult[MemoryData]
# === TypedDict Definitions ===


class RetrieverWorkerOutput(TypedDict):
    """Output from retriever worker."""

    retrieved_docs: str
    retriever_query: str
    all_retrieved_docs: list[Document]
    retrieval_metadata: RetrievalMetadata
    error: str | None


class ReactAgentRetrievalOutput(TypedDict):
    """Output from ReAct agent retrieval."""

    documents: list[Document]
    retrieval_metadata: RetrievalMetadata
    error: str | None


class InformationExtractionOutput(TypedDict):
    """Enhanced information extraction output with proper typing."""

    extracted_info: list[ExtractedInformation] | None
    documents: list[Document]
    processing_time_ms: float | None
    extraction_method: str
    error: str | None


class ContextSummarizationOutput(TypedDict):
    """Enhanced context summarization output with proper typing."""

    summarized_content: list[LangChainDocument]
    documents: list[Document]
    original_length: int
    summarized_length: int
    compression_ratio: float
    summarization_method: str
    processing_time_ms: float | None
    error: str | None


class CitationAttributionOutput(TypedDict):
    """Enhanced citation attribution output with proper typing."""

    citations: list[DocumentCitation]
    documents: list[Document]
    citation_count: int
    citation_method: str
    processing_time_ms: float | None
    error: str | None


class ContextProcessorOutput(TypedDict):
    """Enhanced context processor output with comprehensive typing."""

    documents: list[Document]
    extracted_info: list[ExtractedInformation] | None
    summarized_content: list[LangChainDocument] | None
    citations: list[DocumentCitation] | None
    session_memory: list[MemoryEntry] | None
    processing_metadata: dict[str, str | int | float | bool]
    total_processing_time_ms: float | None
    error: str | None


# === Factory Functions ===


def create_success_result(data: T, execution_time_ms: float | None = None, **metadata: object) -> AgentResult[T]:
    """Create a successful agent result."""
    return AgentResult(data=data, success=True, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


def create_error_result(error: str, execution_time_ms: float | None = None, **metadata: object) -> AgentResult[None]:
    """Create a failed agent result."""
    return AgentResult(data=None, success=False, error=error, execution_time_ms=execution_time_ms, metadata={k: str(v) for k, v in metadata.items()})


def create_extracted_info(
    title: str | None = None, source_url: str | None = None, page_content_snippet: str = "", entities: list[str] | None = None, key_facts: list[str] | None = None, topics: list[str] | None = None, confidence_score: float | None = None, extraction_method: str = "basic", **metadata: object
) -> ExtractedInformation:
    """Factory function to create ExtractedInformation."""
    return ExtractedInformation(
        title=title,
        source_url=source_url,
        page_content_snippet=page_content_snippet,
        entities=entities or [],
        key_facts=key_facts or [],
        topics=topics or [],
        confidence_score=confidence_score,
        extraction_method=extraction_method,
        metadata={k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))},
    )


def create_citation(document_id: str, title: str, source_url: str, page_content_snippet: str, relevance_score: float = 0.0, citation_text: str = "", **metadata: object) -> DocumentCitation:
    """Factory function to create DocumentCitation."""
    return DocumentCitation(
        document_id=document_id,
        title=title,
        source_url=source_url,
        page_content_snippet=page_content_snippet,
        relevance_score=relevance_score,
        citation_text=citation_text,
        metadata={k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))},
    )


def create_memory_entry(id: str, user_id: str, session_id: str, query: str, response: str, timestamp: datetime | None = None, relevance_score: float | None = None, **metadata: object) -> MemoryEntry:
    """Factory function to create MemoryEntry."""
    return MemoryEntry(id=id, user_id=user_id, session_id=session_id, query=query, response=response, timestamp=timestamp or datetime.now(), metadata={k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}, relevance_score=relevance_score)
