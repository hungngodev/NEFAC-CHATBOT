# Exception System Documentation

The exception system provides structured error handling with context, severity levels, and proper error propagation throughout the multi-agent system.

## 📁 Structure

```
backend/src/exceptions/
└── agent_exceptions.py    # Comprehensive exception hierarchy
```

## 🎯 Exception Hierarchy

### Base Exception
```python
class AgentException(Exception):
    """Base exception for all agent errors with structured information."""
    
    def __init__(
        self,
        message: str,
        agent_name: str,
        error_category: ErrorCategory = ErrorCategory.PROCESSING,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
```

**Key Features**:
- **Structured context**: Rich error information for debugging
- **Severity levels**: Categorize error importance
- **Error categories**: Classify error types for handling
- **Original exception**: Preserve underlying error details
- **Agent identification**: Track which agent generated the error

### Error Categories
```python
class ErrorCategory(str, Enum):
    VALIDATION = "validation"        # Input validation failures
    PROCESSING = "processing"        # Core processing errors
    EXTERNAL_SERVICE = "external_service"  # Service connectivity issues
    CONFIGURATION = "configuration"  # Setup and config problems
    TIMEOUT = "timeout"             # Operation timeouts
    RESOURCE = "resource"           # Resource exhaustion
```

### Severity Levels
```python
class ErrorSeverity(str, Enum):
    LOW = "low"          # Minor issues, system continues
    MEDIUM = "medium"    # Moderate issues, may affect quality
    HIGH = "high"        # Serious issues, significant impact
    CRITICAL = "critical" # System-threatening issues
```

## 🔧 Agent-Specific Exceptions

### Complexity Analysis Errors
```python
class ComplexityAnalysisError(AgentException):
    """Raised when complexity analysis fails."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        analysis_method: Optional[str] = None,
        **kwargs
    ):
```

**Usage**:
```python
try:
    complexity_score = analyze_complexity(query)
except Exception as e:
    raise ComplexityAnalysisError(
        "Failed to analyze query complexity",
        query=query,
        analysis_method="rule_based",
        severity=ErrorSeverity.HIGH
    )
```

### Query Understanding Errors
```python
class QueryUnderstandingError(AgentException):
    """Raised when query understanding fails."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        processing_step: Optional[str] = None,
        **kwargs
    ):
```

**Usage**:
```python
try:
    contextualized_query = contextualize_query(query, history)
except Exception as e:
    raise QueryUnderstandingError(
        "Failed to contextualize query",
        query=query,
        processing_step="contextualization",
        error_category=ErrorCategory.PROCESSING
    )
```

### Retrieval Errors
```python
class RetrievalError(AgentException):
    """Raised when document retrieval fails."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        retrieval_method: Optional[str] = None,
        service_name: Optional[str] = None,
        **kwargs
    ):
```

**Usage**:
```python
try:
    documents = vector_service.retrieve(query)
except Exception as e:
    raise RetrievalError(
        "Vector retrieval failed",
        query=query,
        retrieval_method="dense",
        service_name="qdrant",
        error_category=ErrorCategory.EXTERNAL_SERVICE,
        severity=ErrorSeverity.HIGH
    )
```

### Generation Errors
```python
class GenerationError(AgentException):
    """Raised when answer generation fails."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        context_length: Optional[int] = None,
        model_name: Optional[str] = None,
        **kwargs
    ):
```

## 🏥 Service-Specific Exceptions

### External Service Errors
```python
class VectorStoreError(AgentException):
    """Raised when vector store operations fail."""
    
class KeywordSearchError(AgentException):
    """Raised when keyword search operations fail."""
    
class GraphDatabaseError(AgentException):
    """Raised when graph database operations fail."""
    
class LLMServiceError(AgentException):
    """Raised when LLM service operations fail."""
```

**Automatic Categorization**:
```python
class VectorStoreError(AgentException):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message, 
            agent_name="VectorStore",
            error_category=ErrorCategory.EXTERNAL_SERVICE,
            **kwargs
        )
```

### Configuration Errors
```python
class ConfigurationError(AgentException):
    """Raised when configuration is invalid."""
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None, 
        **kwargs
    ):
        context = kwargs.get('context', {})
        context.update({"config_key": config_key})
        kwargs['context'] = context
        super().__init__(
            message,
            agent_name="Configuration",
            error_category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
```

## 🛠️ Error Handling Utilities

### Exception Conversion
```python
def handle_agent_exception(
    exception: Exception,
    agent_name: str,
    context: Optional[Dict[str, Any]] = None
) -> AgentException:
    """Convert generic exceptions to AgentException."""
    if isinstance(exception, AgentException):
        return exception
    
    return AgentException(
        message=str(exception),
        agent_name=agent_name,
        context=context,
        original_exception=exception
    )
```

### Context Creation
```python
def create_error_context(
    query: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **additional_context
) -> Dict[str, Any]:
    """Create standardized error context."""
    context = {
        "query": query,
        "user_id": user_id,
        "session_id": session_id
    }
    context.update(additional_context)
    return {k: v for k, v in context.items() if v is not None}
```

## 📊 Error Information

### Structured Error Data
```python
exception = RetrievalError(
    "Failed to retrieve documents",
    query="What is FOIA?",
    retrieval_method="vector",
    service_name="qdrant"
)

error_dict = exception.to_dict()
# Returns:
{
    "error_type": "RetrievalError",
    "message": "Failed to retrieve documents",
    "agent_name": "Retriever",
    "error_category": "external_service",
    "severity": "medium",
    "context": {
        "query": "What is FOIA?",
        "retrieval_method": "vector",
        "service_name": "qdrant"
    },
    "original_exception": None
}
```

### Error Logging
```python
try:
    result = risky_operation()
except AgentException as e:
    logger.error(
        f"Agent error in {e.agent_name}: {e.message}",
        extra={
            "error_category": e.error_category.value,
            "severity": e.severity.value,
            "context": e.context,
            "agent_name": e.agent_name
        }
    )
```

## 🔄 Error Handling Patterns

### Agent Error Handling
```python
class MyAgent:
    def process(self, state: AgentState) -> AgentResult:
        try:
            # Agent processing logic
            result = self._do_processing(state)
            return create_success_result(data=result)
            
        except MySpecificError:
            # Re-raise specific errors
            raise
            
        except Exception as e:
            # Convert unexpected errors
            error = handle_agent_exception(e, self.agent_name, {
                "query": state.user_query,
                "processing_step": "main_processing"
            })
            return create_error_result(error=str(error))
```

### Service Error Handling
```python
def get_retriever(self):
    try:
        return self._initialize_retriever()
    except ConnectionError as e:
        raise VectorStoreError(
            f"Failed to connect to vector store: {e}",
            service_name="qdrant",
            severity=ErrorSeverity.HIGH
        )
    except AuthenticationError as e:
        raise VectorStoreError(
            f"Authentication failed: {e}",
            service_name="qdrant",
            error_category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL
        )
```

### Graceful Degradation
```python
try:
    # Primary operation
    result = primary_service.operation()
except ExternalServiceError as e:
    logger.warning(f"Primary service failed: {e}, falling back")
    try:
        # Fallback operation
        result = fallback_service.operation()
    except Exception as fallback_error:
        # Final error with context
        raise ProcessingError(
            "Both primary and fallback services failed",
            primary_error=str(e),
            fallback_error=str(fallback_error),
            severity=ErrorSeverity.CRITICAL
        )
```

## 🧪 Testing Error Scenarios

### Exception Testing
```python
def test_retrieval_error_handling():
    with pytest.raises(RetrievalError) as exc_info:
        agent.retrieve_documents(invalid_state)
    
    error = exc_info.value
    assert error.agent_name == "Retriever"
    assert error.error_category == ErrorCategory.VALIDATION
    assert "query" in error.context
```

### Error Context Validation
```python
def test_error_context():
    try:
        raise QueryUnderstandingError(
            "Test error",
            query="test query",
            processing_step="validation"
        )
    except QueryUnderstandingError as e:
        assert e.context["query"] == "test query"
        assert e.context["processing_step"] == "validation"
        assert e.agent_name == "QueryUnderstanding"
```

### Error Serialization
```python
def test_error_serialization():
    error = RetrievalError("Test error", query="test")
    error_dict = error.to_dict()
    
    assert error_dict["error_type"] == "RetrievalError"
    assert error_dict["context"]["query"] == "test"
    assert error_dict["agent_name"] == "Retriever"
```

This exception system provides comprehensive error handling with rich context, proper categorization, and structured information for debugging and monitoring throughout the multi-agent system.