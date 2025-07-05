"""
Input Validation Utilities
Provides comprehensive validation for agent inputs and configurations.
"""

import re
from typing import Dict, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, validator

from ..exceptions.agent_exceptions import InputValidationError
from ..schemas.agent_types import QueryIntent, RetrievalMethod


class QueryValidation(BaseModel):
    """Validation model for user queries."""

    query: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    thread_id: Optional[str] = Field(None, max_length=100)

    @validator("query")
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty or only whitespace")

        # Check for potentially malicious content
        suspicious_patterns = [
            r"<script.*?>.*?</script>",  # Script tags
            r"javascript:",  # JavaScript URLs
            r"on\w+\s*=",  # Event handlers
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query contains potentially malicious content")

        return v.strip()

    @validator("user_id")
    def validate_user_id(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("User ID can only contain alphanumeric characters, underscores, and hyphens")
        return v


class ComplexityAnalysisValidation(BaseModel):
    """Validation for complexity analysis inputs."""

    query: str = Field(..., min_length=1, max_length=10000)
    chat_history: Optional[List[BaseMessage]] = Field(default_factory=list)

    @validator("chat_history")
    def validate_chat_history(cls, v):
        if v is None:
            return []

        if len(v) > 100:  # Reasonable limit for chat history
            raise ValueError("Chat history too long (max 100 messages)")

        return v


class RetrievalValidation(BaseModel):
    """Validation for retrieval inputs."""

    query: str = Field(..., min_length=1, max_length=10000)
    retrieval_methods: List[RetrievalMethod] = Field(default_factory=lambda: [RetrievalMethod.DENSE])
    weights: Optional[List[float]] = Field(None)
    max_documents: int = Field(default=10, ge=1, le=100)

    @validator("weights")
    def validate_weights(cls, v, values):
        if v is None:
            return None

        methods = values.get("retrieval_methods", [])
        if len(v) != len(methods):
            raise ValueError("Number of weights must match number of retrieval methods")

        if not all(0.0 <= weight <= 1.0 for weight in v):
            raise ValueError("All weights must be between 0.0 and 1.0")

        if abs(sum(v) - 1.0) > 0.001:  # Allow small floating point errors
            raise ValueError("Weights must sum to 1.0")

        return v


class ReActValidation(BaseModel):
    """Validation for ReAct worker inputs."""

    query: str = Field(..., min_length=1, max_length=10000)
    max_steps: int = Field(default=3, ge=1, le=10)
    chat_history: Optional[List[BaseMessage]] = Field(default_factory=list)

    @validator("max_steps")
    def validate_max_steps(cls, v):
        if v > 10:
            raise ValueError("Maximum steps cannot exceed 10 to prevent infinite loops")
        return v


class GenerationValidation(BaseModel):
    """Validation for answer generation inputs."""

    query: str = Field(..., min_length=1, max_length=10000)
    context: str = Field(..., max_length=50000)  # Reasonable context limit
    intent: QueryIntent = Field(default=QueryIntent.GENERAL_QUERY)

    @validator("context")
    def validate_context(cls, v):
        if not v.strip():
            raise ValueError("Context cannot be empty")
        return v.strip()


# Validation functions
def validate_query_input(query: str, user_id: str, session_id: Optional[str] = None, thread_id: Optional[str] = None) -> QueryValidation:
    """Validate basic query input."""
    try:
        return QueryValidation(query=query, user_id=user_id, session_id=session_id, thread_id=thread_id)
    except ValueError as e:
        raise InputValidationError(f"Invalid query input: {e}", field_name="query_input", field_value=query)


def validate_complexity_input(query: str, chat_history: Optional[List[BaseMessage]] = None) -> ComplexityAnalysisValidation:
    """Validate complexity analysis input."""
    try:
        return ComplexityAnalysisValidation(query=query, chat_history=chat_history or [])
    except ValueError as e:
        raise InputValidationError(f"Invalid complexity analysis input: {e}", field_name="complexity_input", field_value=query)


def validate_retrieval_input(query: str, retrieval_methods: Optional[List[str]] = None, weights: Optional[List[float]] = None, max_documents: int = 10) -> RetrievalValidation:
    """Validate retrieval input."""
    try:
        # Convert string methods to enum
        if retrieval_methods:
            methods = [RetrievalMethod(method.lower()) for method in retrieval_methods]
        else:
            methods = [RetrievalMethod.DENSE]

        return RetrievalValidation(query=query, retrieval_methods=methods, weights=weights, max_documents=max_documents)
    except ValueError as e:
        raise InputValidationError(f"Invalid retrieval input: {e}", field_name="retrieval_input", field_value=query)


def validate_react_input(query: str, max_steps: int = 3, chat_history: Optional[List[BaseMessage]] = None) -> ReActValidation:
    """Validate ReAct worker input."""
    try:
        return ReActValidation(query=query, max_steps=max_steps, chat_history=chat_history or [])
    except ValueError as e:
        raise InputValidationError(f"Invalid ReAct input: {e}", field_name="react_input", field_value=query)


def validate_generation_input(query: str, context: str, intent: Optional[str] = None) -> GenerationValidation:
    """Validate generation input."""
    try:
        # Convert string intent to enum
        if intent:
            intent_enum = QueryIntent(intent.lower())
        else:
            intent_enum = QueryIntent.GENERAL_QUERY

        return GenerationValidation(query=query, context=context, intent=intent_enum)
    except ValueError as e:
        raise InputValidationError(f"Invalid generation input: {e}", field_name="generation_input", field_value=query)


def validate_environment_variables(required_vars: List[str]) -> None:
    """Validate that required environment variables are set."""
    import os

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise InputValidationError(f"Missing required environment variables: {missing_vars}", field_name="environment_variables", field_value=str(missing_vars))


def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    if not text:
        return ""

    # Remove potentially dangerous characters/patterns
    sanitized = text.strip()

    # Remove null bytes
    sanitized = sanitized.replace("\x00", "")

    # Limit length
    if len(sanitized) > 10000:
        sanitized = sanitized[:10000]

    return sanitized


def validate_pagination(limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, int]:
    """Validate pagination parameters."""
    if limit is None:
        limit = 10
    if offset is None:
        offset = 0

    if limit < 1 or limit > 100:
        raise InputValidationError("Limit must be between 1 and 100", field_name="limit", field_value=str(limit))

    if offset < 0:
        raise InputValidationError("Offset must be non-negative", field_name="offset", field_value=str(offset))

    return {"limit": limit, "offset": offset}
