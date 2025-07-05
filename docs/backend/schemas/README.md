# Schemas & Type System Documentation

The schemas module provides the foundation for type safety throughout the multi-agent system.

## 📁 Structure

```
backend/src/schemas/
├── agent_types.py      # Strongly typed result containers and data models
├── agent_protocols.py  # Protocol-based interfaces for all agents
├── state.py           # Unified state management
├── main.py            # Legacy compatibility types
└── metadata.py        # Metadata definitions
```

## 🎯 Core Components

### Agent Types (`agent_types.py`)

Provides strongly typed result containers that eliminate `Dict[str, Any]` usage:

#### Base Result Type
```python
@dataclass
class AgentResult(Generic[T]):
    data: T
    success: bool = True
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)
```

#### Agent-Specific Data Types
```python
@dataclass
class QueryComplexityData:
    complexity_score: float = Field(ge=0.0, le=1.0)
    reasoning_required: bool
    multi_hop_needed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    complexity_category: ComplexityCategory
    recommended_route: RecommendedRoute

@dataclass
class QueryUnderstandingData:
    contextualized_query: str
    intent: QueryIntent
    entities: List[str]
    structured_query: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

@dataclass
class RetrievalData:
    documents: List[Document]
    retrieval_methods_used: List[RetrievalMethod]
    total_documents_found: int
    deduplication_applied: bool
    reranking_applied: bool
    retrieval_time_ms: Optional[float] = None
```

#### Enums for Type Safety
```python
class ComplexityCategory(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"

class QueryIntent(str, Enum):
    DOCUMENT_REQUEST = "document_request"
    STRUCTURED_GRAPH_QUERY = "structured_graph_query"
    GENERAL_QUERY = "general_query"

class RetrievalMethod(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    GRAPH = "graph"
```

### Agent Protocols (`agent_protocols.py`)

Defines interfaces using Python protocols for type safety and contract enforcement:

```python
@runtime_checkable
class ComplexityAnalyzerProtocol(Protocol):
    def analyze_complexity(
        self, 
        query: str, 
        chat_history: Optional[List[BaseMessage]] = None
    ) -> QueryComplexityResult: ...

@runtime_checkable
class ContextualizerProtocol(Protocol):
    def process_query(
        self, 
        state: AgentState, 
        model: ChatOpenAI
    ) -> QueryUnderstandingResult: ...

@runtime_checkable
class RetrieverProtocol(Protocol):
    def retrieve_documents(self, state: AgentState) -> RetrievalResult: ...
```

### State Management (`state.py`)

Unified state object that flows through the entire system:

```python
class AgentState(BaseModel):
    # Core conversation fields
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    user_query: str = Field(description="Current user query")
    
    # User and session management
    user_id: str = Field(default="default_user")
    session_id: Optional[str] = Field(default=None)
    thread_id: Optional[str] = Field(default=None)
    
    # Supervisor and routing
    supervisor_decision: Optional[str] = Field(default=None)
    query_complexity: Optional[float] = Field(default=None)
    
    # Contextualizer
    contextualized_query: Optional[str] = Field(default=None)
    
    # Memory integration
    memory_summary: Optional[str] = Field(default=None)
    relevant_memories: Optional[List[Dict[str, Any]]] = Field(default=None)
    
    # Retrieval
    retrieval_selection: Optional[Dict[str, Union[List[str], List[float]]]] = Field(default=None)
    retrieved_docs: Optional[str] = Field(default=None)
    all_retrieved_docs: Optional[List[Any]] = Field(default=None)
    
    # Final answer
    final_answer: Optional[str] = Field(default=None)
    
    # Error handling
    error: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0)
```

## 🔧 Usage Patterns

### Creating Typed Results
```python
# Success result
return create_success_result(
    data=QueryComplexityData(
        complexity_score=0.7,
        reasoning_required=True,
        confidence=0.9
    ),
    execution_time_ms=150.5
)

# Error result
return create_error_result(
    error="Analysis failed: invalid input",
    execution_time_ms=50.0
)
```

### Protocol Implementation
```python
class MyAgent:
    def process_query(self, state: AgentState, model: ChatOpenAI) -> QueryUnderstandingResult:
        # Implementation automatically satisfies ContextualizerProtocol
        pass

# Runtime checking
assert isinstance(my_agent, ContextualizerProtocol)
```

### State Transitions
```python
def create_initial_state(
    user_query: str,
    user_id: str = "default_user",
    session_id: Optional[str] = None
) -> AgentState:
    return AgentState(
        user_query=user_query,
        user_id=user_id,
        session_id=session_id
    )
```

## ✅ Benefits

### Type Safety
- **Compile-time error detection** with mypy
- **IDE autocomplete** and type hints
- **Runtime validation** with Pydantic
- **Clear contracts** between components

### Maintainability
- **Self-documenting code** through types
- **Easier refactoring** with type checking
- **Consistent interfaces** across agents
- **Reduced debugging time**

### Performance
- **Execution tracking** built into result types
- **Structured metadata** for monitoring
- **Efficient serialization** with Pydantic
- **Memory optimization** through proper typing

## 🧪 Testing

The type system enables comprehensive testing:

```python
def test_agent_result_typing():
    result = create_success_result(
        data=QueryComplexityData(complexity_score=0.5),
        execution_time_ms=100.0
    )
    
    assert result.is_success
    assert result.data.complexity_score == 0.5
    assert result.execution_time_ms == 100.0

def test_protocol_compliance():
    agent = MyComplexityAnalyzer()
    assert isinstance(agent, ComplexityAnalyzerProtocol)
```

This type system provides the foundation for a robust, maintainable, and type-safe multi-agent system.