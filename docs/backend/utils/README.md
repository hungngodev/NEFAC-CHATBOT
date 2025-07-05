# Utils Documentation

The utils module provides validation, helper functions, and utilities that support the multi-agent system.

## 📁 Structure

```
backend/src/utils/
└── validation.py    # Input validation and data sanitization
```

## 🎯 Core Components

### Input Validation (`validation.py`)

Provides comprehensive input validation using Pydantic models to ensure data integrity and security.

#### Validation Models

**Query Validation**:
```python
class QueryValidation(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)
    thread_id: Optional[str] = Field(None, max_length=100)
    
    @validator('query')
    def validate_query(cls, v):
        # Security: Check for potentially malicious content
        # Length validation and sanitization
        return v.strip()
```

**Retrieval Validation**:
```python
class RetrievalValidation(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    retrieval_methods: List[RetrievalMethod] = Field(default_factory=lambda: [RetrievalMethod.DENSE])
    weights: Optional[List[float]] = Field(None)
    max_documents: int = Field(default=10, ge=1, le=100)
    
    @validator('weights')
    def validate_weights(cls, v, values):
        # Ensure weights sum to 1.0 and match method count
        return v
```

#### Security Functions

**Input Sanitization**:
```python
def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks."""
    # Remove potentially dangerous characters/patterns
    # Limit length and remove null bytes
    return sanitized_text

def validate_environment_variables(required_vars: List[str]) -> None:
    """Validate that required environment variables are set."""
    # Check for missing environment variables
    # Raise InputValidationError if any are missing
```

## 🛡️ Security Features

- **XSS Prevention**: Removes script tags and JavaScript URLs
- **Injection Prevention**: Sanitizes special characters  
- **Length Limiting**: Prevents buffer overflow attacks
- **Input Validation**: Comprehensive parameter checking

## 🧪 Testing

Comprehensive validation testing with security scenario coverage and error handling validation.