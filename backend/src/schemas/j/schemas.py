"""
Enhanced Pydantic Schemas with Comprehensive Type Safety
This file contains enhanced versions of all schemas with proper validation,
descriptions, and static type hints.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, validator

# === Core Response Schemas ===


class APIResponse(BaseModel):
    """Base API response schema with consistent structure."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, use_enum_values=True)

    success: bool = Field(description="Whether the request was successful")
    message: str = Field(description="Human-readable response message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class ErrorResponse(APIResponse):
    """Error response schema with detailed error information."""

    success: bool = Field(default=False, description="Always false for error responses")
    error_code: str = Field(description="Machine-readable error code")
    details: Optional[Dict[str, Union[str, int, float, bool, List[str]]]] = Field(default=None, description="Additional error details")


class LoadingStatusResponse(BaseModel):
    """Enhanced loading status response with validation."""

    model_config = ConfigDict(validate_assignment=True)

    current: int = Field(ge=0, description="Current progress count")
    total: int = Field(gt=0, description="Total items to process")
    status: str = Field(description="Current status message")
    is_loading: bool = Field(description="Whether loading is in progress")

    @validator("current")
    def current_not_exceed_total(cls, v, values):
        if "total" in values and v > values["total"]:
            raise ValueError("Current cannot exceed total")
        return v


# === Enhanced Citation and Search Schemas ===


class Citation(BaseModel):
    """Enhanced citation with validation and metadata."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1, description="Unique identifier for the citation")
    context: str = Field(min_length=1, description="The citation used to generate the search result")
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Relevance score (0-1)")
    source_type: Optional[Literal["document", "web", "database"]] = Field(default=None, description="Type of source")


class SearchResult(BaseModel):
    """Enhanced search result with comprehensive metadata."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    title: str = Field(min_length=1, description="The title of the search result")
    link: str = Field(description="The link to the source of search result")
    summary: str = Field(min_length=1, description="A brief summary of the search result and relevance to prompt")
    citations: List[Citation] = Field(description="A list of citations used to generate the search result")
    type: Optional[str] = Field(default=None, description="Type of search result")
    timestamp_seconds: Optional[int] = Field(default=None, ge=0, description="Timestamp in seconds")
    content: Optional[str] = Field(default=None, description="Full content of the search result")
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score")

    @validator("link")
    def validate_link(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("/")):
            raise ValueError("Link must be a valid URL or path")
        return v


class SearchResponse(BaseModel):
    """Enhanced search response with metadata."""

    model_config = ConfigDict(validate_assignment=True)

    results: List[SearchResult] = Field(description="A list of search results")
    total_results: int = Field(ge=0, description="Total number of results found")
    query_time_ms: Optional[int] = Field(default=None, ge=0, description="Query execution time in milliseconds")

    @validator("total_results")
    def validate_total_results(cls, v, values):
        if "results" in values and v != len(values["results"]):
            raise ValueError("total_results must match length of results list")
        return v


# === Enhanced Event Schemas ===


class BaseEvent(BaseModel):
    """Base event schema with common fields."""

    model_config = ConfigDict(validate_assignment=True)

    order: int = Field(ge=0, description="Event order in sequence")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")
    event_id: str = Field(description="Unique event identifier")


class ContextEvent(BaseEvent):
    """Enhanced context event with validation."""

    context: List[SearchResult] = Field(description="List of contextual search results")
    context_type: Optional[Literal["retrieval", "memory", "external"]] = Field(default="retrieval", description="Type of context")


class ReformulatedEvent(BaseEvent):
    """Enhanced reformulated query event."""

    reformulated: str = Field(min_length=1, description="Reformulated query text")
    original_query: Optional[str] = Field(default=None, description="Original query for comparison")
    reformulation_method: Optional[str] = Field(default=None, description="Method used for reformulation")


class MessageEvent(BaseEvent):
    """Enhanced message event with metadata."""

    message: str = Field(min_length=1, description="Message content")
    message_type: Optional[Literal["info", "warning", "error", "success"]] = Field(default="info", description="Message type")
    source: Optional[str] = Field(default=None, description="Source of the message")


# === Enhanced Classification Schemas ===


class IntentClassification(BaseModel):
    """Enhanced intent classification with confidence."""

    model_config = ConfigDict(use_enum_values=True)

    intent: Literal["document request", "general"] = Field(description="Classify the user's intent. If they are asking for information that could be found in NEFAC's documents, classify as 'document request'. Otherwise, classify as 'general'.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for the classification")
    reasoning: Optional[str] = Field(default=None, description="Reasoning behind the classification")


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config = ConfigDict(use_enum_values=True)

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
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence in method selection")
    fallback_method: Optional[str] = Field(default="default", description="Fallback method if primary fails")


class RetrievalSelection(BaseModel):
    """Enhanced retrieval selection with validation."""

    model_config = ConfigDict(validate_assignment=True)

    methods: List[Literal["graph", "dense", "sparse"]] = Field(
        min_items=1,
        description=("Which retrieval methods to apply—any combination of:\n" "• graph  – Neo4j knowledge-graph retriever\n" "• dense  – Qdrant semantic vector retriever\n" "• sparse – Elasticsearch BM25 keyword retriever"),
    )
    weights: List[float] = Field(
        min_items=1,
        description=("A parallel list of weights for each method, summing to 1.0 if possible.\n" "If lengths mismatch or sum != 1, weights will be normalized equally."),
    )

    @validator("weights")
    def validate_weights(cls, v, values):
        if "methods" in values and len(v) != len(values["methods"]):
            raise ValueError("weights must have same length as methods")
        if all(w >= 0 for w in v) and sum(v) > 0:
            # Normalize weights to sum to 1.0
            total = sum(v)
            return [w / total for w in v]
        raise ValueError("weights must be positive and sum to > 0")


# === Enhanced Reasoning and Validation Schemas ===


class MultiStepReasoning(BaseModel):
    """Enhanced multi-step reasoning with metadata."""

    model_config = ConfigDict(validate_assignment=True)

    reasoning_steps: List[str] = Field(
        min_items=1,
        description="A list of reasoning steps to answer the user's query.",
    )
    step_types: Optional[List[str]] = Field(default=None, description="Types of each reasoning step")
    confidence_scores: Optional[List[float]] = Field(default=None, description="Confidence for each step")

    @validator("step_types")
    def validate_step_types(cls, v, values):
        if v and "reasoning_steps" in values and len(v) != len(values["reasoning_steps"]):
            raise ValueError("step_types must match length of reasoning_steps")
        return v


class Validation(BaseModel):
    """Enhanced validation with detailed feedback."""

    model_config = ConfigDict(validate_assignment=True)

    is_valid: bool = Field(description="Whether the generated answer is valid or not.")
    reasoning: str = Field(min_length=1, description="The reasoning behind the validation.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the validation")
    validation_criteria: Optional[List[str]] = Field(default=None, description="Criteria used for validation")
    suggestions: Optional[List[str]] = Field(default=None, description="Suggestions for improvement if invalid")


# === Enhanced Metadata Schemas ===


class EnhancedBaseMetadata(BaseModel):
    """Enhanced base metadata with comprehensive validation."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="allow")  # Allow additional fields for flexibility

    id: Union[int, str] = Field(description="Unique identifier for the document")
    title: str = Field(min_length=1, description="Document title")
    filename: str = Field(min_length=1, description="Original filename")
    source_url: str = Field(description="Source URL of the document")
    date: str = Field(description="Document creation/publication date")
    modified: Optional[str] = Field(default=None, description="Last modification date")
    mime_type: Optional[str] = Field(default=None, description="MIME type of the document")
    file_size: Optional[int] = Field(default=None, ge=0, description="File size in bytes")
    download_date: Optional[str] = Field(default=None, description="Date when document was downloaded")
    crawler_version: Optional[str] = Field(default=None, description="Version of crawler used")

    @validator("source_url")
    def validate_source_url(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("file://")):
            raise ValueError("source_url must be a valid URL")
        return v


class EnhancedAuthorMetadata(BaseModel):
    """Enhanced author metadata with validation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Author's full name")
    slug: str = Field(min_length=1, description="URL-friendly author identifier")
    uri: str = Field(description="Author's URI/profile link")
    description: Optional[str] = Field(default=None, description="Author biography or description")
    email: Optional[str] = Field(default=None, description="Author's email address")

    @validator("email")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


# === Factory Functions ===


def create_error_response(message: str, error_code: str, details: Optional[Dict[str, Union[str, int, float, bool, List[str]]]] = None) -> ErrorResponse:
    """Factory function to create standardized error responses."""
    return ErrorResponse(message=message, error_code=error_code, details=details)


def create_success_response(message: str) -> APIResponse:
    """Factory function to create standardized success responses."""
    return APIResponse(success=True, message=message)
