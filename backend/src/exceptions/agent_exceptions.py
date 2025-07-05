"""
Typed Exception Hierarchy for Multi-Agent System
Provides specific error types for better error handling and debugging.
"""

from enum import Enum
from typing import Any, Dict, Optional


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


class AgentException(Exception):
    """
    Base exception for all agent errors.
    Provides structured error information for better debugging and monitoring.
    """

    def __init__(self, message: str, agent_name: str, error_category: ErrorCategory = ErrorCategory.PROCESSING, severity: ErrorSeverity = ErrorSeverity.MEDIUM, context: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.agent_name = agent_name
        self.error_category = error_category
        self.severity = severity
        self.context = context or {}
        self.original_exception = original_exception

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/monitoring."""
        return {"error_type": self.__class__.__name__, "message": str(self), "agent_name": self.agent_name, "error_category": self.error_category.value, "severity": self.severity.value, "context": self.context, "original_exception": str(self.original_exception) if self.original_exception else None}


# Specific agent exceptions
class ComplexityAnalysisError(AgentException):
    """Raised when complexity analysis fails."""

    def __init__(self, message: str, query: Optional[str] = None, analysis_method: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "analysis_method": analysis_method})
        kwargs["context"] = context
        super().__init__(message, agent_name="ComplexityAnalyzer", **kwargs)


class QueryUnderstandingError(AgentException):
    """Raised when query understanding fails."""

    def __init__(self, message: str, query: Optional[str] = None, processing_step: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "processing_step": processing_step})
        kwargs["context"] = context
        super().__init__(message, agent_name="QueryUnderstanding", **kwargs)


class RetrievalError(AgentException):
    """Raised when document retrieval fails."""

    def __init__(self, message: str, query: Optional[str] = None, retrieval_method: Optional[str] = None, service_name: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "retrieval_method": retrieval_method, "service_name": service_name})
        kwargs["context"] = context
        super().__init__(message, agent_name="Retriever", **kwargs)


class ReasoningError(AgentException):
    """Raised when ReAct reasoning fails."""

    def __init__(self, message: str, query: Optional[str] = None, reasoning_step: Optional[int] = None, sub_question: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "reasoning_step": reasoning_step, "sub_question": sub_question})
        kwargs["context"] = context
        super().__init__(message, agent_name="ReActWorker", **kwargs)


class GenerationError(AgentException):
    """Raised when answer generation fails."""

    def __init__(self, message: str, query: Optional[str] = None, context_length: Optional[int] = None, model_name: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "context_length": context_length, "model_name": model_name})
        kwargs["context"] = context
        super().__init__(message, agent_name="Generator", **kwargs)


class ValidationError(AgentException):
    """Raised when answer validation fails."""

    def __init__(self, message: str, query: Optional[str] = None, answer: Optional[str] = None, validation_criteria: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"query": query, "answer": answer, "validation_criteria": validation_criteria})
        kwargs["context"] = context
        super().__init__(message, agent_name="Validator", **kwargs)


class MemoryError(AgentException):
    """Raised when memory operations fail."""

    def __init__(self, message: str, operation: Optional[str] = None, user_id: Optional[str] = None, memory_type: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"operation": operation, "user_id": user_id, "memory_type": memory_type})
        kwargs["context"] = context
        super().__init__(message, agent_name="MemoryManager", **kwargs)


# Service-specific exceptions
class VectorStoreError(AgentException):
    """Raised when vector store operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, agent_name="VectorStore", error_category=ErrorCategory.EXTERNAL_SERVICE, **kwargs)


class KeywordSearchError(AgentException):
    """Raised when keyword search operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, agent_name="KeywordSearch", error_category=ErrorCategory.EXTERNAL_SERVICE, **kwargs)


class GraphDatabaseError(AgentException):
    """Raised when graph database operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, agent_name="GraphDatabase", error_category=ErrorCategory.EXTERNAL_SERVICE, **kwargs)


class LLMServiceError(AgentException):
    """Raised when LLM service operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, agent_name="LLMService", error_category=ErrorCategory.EXTERNAL_SERVICE, **kwargs)


# Configuration and validation exceptions
class ConfigurationError(AgentException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"config_key": config_key})
        kwargs["context"] = context
        super().__init__(message, agent_name="Configuration", error_category=ErrorCategory.CONFIGURATION, severity=ErrorSeverity.HIGH, **kwargs)


class InputValidationError(AgentException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field_name: Optional[str] = None, field_value: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"field_name": field_name, "field_value": field_value})
        kwargs["context"] = context
        super().__init__(message, agent_name="InputValidator", error_category=ErrorCategory.VALIDATION, **kwargs)


class TimeoutError(AgentException):
    """Raised when operations timeout."""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, operation: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        context.update({"timeout_seconds": timeout_seconds, "operation": operation})
        kwargs["context"] = context
        super().__init__(message, agent_name="TimeoutHandler", error_category=ErrorCategory.TIMEOUT, severity=ErrorSeverity.HIGH, **kwargs)


# Helper functions for exception handling
def handle_agent_exception(exception: Exception, agent_name: str, context: Optional[Dict[str, Any]] = None) -> AgentException:
    """Convert generic exceptions to AgentException."""
    if isinstance(exception, AgentException):
        return exception

    return AgentException(message=str(exception), agent_name=agent_name, context=context, original_exception=exception)


def create_error_context(query: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None, **additional_context) -> Dict[str, Any]:
    """Create standardized error context."""
    context = {"query": query, "user_id": user_id, "session_id": session_id}
    context.update(additional_context)
    return {k: v for k, v in context.items() if v is not None}
