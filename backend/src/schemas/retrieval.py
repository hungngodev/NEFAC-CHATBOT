"""
Retrieval System Schemas
Centralized Pydantic models for all retrieval-related functionality.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# --- Graph Retrieval Schemas ---


class Entities(BaseModel):
    """Schema for entity extraction from text."""

    names: List[str] = Field(..., description="Canonical entity names (person, org, etc.) in the text.")
    types: Optional[List[str]] = Field(None, description="Entity types (Person, Organization, etc.)")


# --- Retrieval Strategy Schemas ---


class RetrievalStrategy(BaseModel):
    """Structured retrieval strategy selection."""

    methods: List[str] = Field(description="List of retrieval methods to use")
    weights: List[float] = Field(description="Weights for each method")
    reasoning: str = Field(description="Explanation of strategy choice")
    query_expansion: bool = Field(default=False, description="Whether to expand the query")
    rerank: bool = Field(default=True, description="Whether to apply reranking")


# --- Query Processing Schemas ---


class QueryContext(BaseModel):
    """Context information for query processing."""

    entities: List[dict] = Field(default_factory=list, description="Extracted entities from query")
    metadata_filters: dict = Field(default_factory=dict, description="Metadata filters to apply")
    priorities: List[str] = Field(default_factory=list, description="Priority ordering for results")
    structured_query: Optional[str] = Field(None, description="Structured query for direct execution")
    statistical_query: Optional[str] = Field(None, description="Statistical query for aggregations")


# --- Retrieval Results Schemas ---


class RetrievalResult(BaseModel):
    """Result from retrieval operation."""

    documents: List[dict] = Field(default_factory=list, description="Retrieved documents")
    strategy_used: Optional[str] = Field(None, description="Strategy that was used for retrieval")
    total_found: int = Field(default=0, description="Total number of documents found")
    error: Optional[str] = Field(None, description="Error message if retrieval failed")


class DocumentMetadata(BaseModel):
    """Metadata for retrieved documents."""

    source: str = Field(description="Source of the document")
    retrieval_method: str = Field(description="Method used to retrieve this document")
    retrieval_rank: int = Field(description="Rank in retrieval results")
    stream_tag: str = Field(description="Tag for streaming identification")
    entity: Optional[str] = Field(None, description="Associated entity if applicable")
    confidence_score: Optional[float] = Field(None, description="Confidence score for relevance")
