"""
Supervisor System Schemas
Centralized Pydantic models for supervisor-related functionality.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# --- Query Complexity Schemas ---


class QueryComplexity(BaseModel):
    """Query complexity analysis with detailed breakdown."""

    complexity_score: float = Field(ge=0.0, le=1.0, description="Overall complexity score")
    reasoning_required: bool = Field(description="Whether multi-step reasoning is needed")
    multi_hop_needed: bool = Field(description="Whether multiple retrieval steps are required")
    tool_usage_required: bool = Field(description="Whether tools are needed")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in assessment")

    # Detailed metrics
    linguistic_complexity: float = Field(ge=0.0, le=1.0, description="Language and syntax complexity")
    domain_complexity: float = Field(ge=0.0, le=1.0, description="Legal domain complexity")
    reasoning_complexity: float = Field(ge=0.0, le=1.0, description="Reasoning requirements")
    temporal_complexity: float = Field(ge=0.0, le=1.0, description="Time-based query complexity")

    # Classification
    complexity_category: str = Field(description="Simple, Medium, or Complex")
    recommended_route: str = Field(description="Recommended processing route")
    reasoning: str = Field(description="Explanation of complexity assessment")


# --- Validation Schemas ---


class Validation(BaseModel):
    """Validation of the answer against the context."""

    is_valid: bool = Field(description="Whether the answer is valid and supported by the context.")
    reason: str = Field(description="The reason for the validation result.")
    confidence_score: Optional[float] = Field(None, description="Confidence in validation (0-1)")
    missing_information: Optional[List[str]] = Field(None, description="Information missing from context")
    contradictions: Optional[List[str]] = Field(None, description="Contradictions found in answer")


# --- Strategy Selection Schemas ---


class StrategyRecommendation(BaseModel):
    """Recommended strategy based on complexity analysis."""

    primary_strategy: str = Field(description="Primary processing strategy to use")
    fallback_strategies: List[str] = Field(description="Alternative strategies if primary fails")
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
    error_message: Optional[str] = Field(None, description="Error message if failed")
