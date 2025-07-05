# Core Agents Documentation

The core agents module implements the hierarchical multi-agent system with proper typing, error handling, and clean architecture.

## 📁 Structure

```
backend/src/core/agents/
├── supervisor/           # Complexity analysis and routing
│   ├── complexity_analyzer.py
│   ├── generator.py
│   ├── strategy.py
│   └── validation.py
├── contextualizer/       # Query understanding and processing
│   ├── query_understanding.py
│   └── history_manager.py
├── workers/             # Specialized worker agents
│   ├── retriever/       # Document retrieval
│   └── react/           # Multi-step reasoning
└── tools/               # Supporting tools and utilities
    ├── retrieval/       # Retrieval implementations
    ├── memory/          # Memory management
    └── *.py             # Various processing tools
```

## 🎯 Agent Hierarchy

### Level 1: Supervisor Layer

#### Complexity Analyzer (`supervisor/complexity_analyzer.py`)
**Purpose**: Analyzes query complexity and determines optimal routing strategy.

```python
class ComplexityAnalyzer:
    def analyze_complexity(
        self, 
        query: str, 
        chat_history: Optional[List[BaseMessage]] = None
    ) -> QueryComplexityResult:
        """Analyze query complexity across multiple dimensions."""
```

**Key Features**:
- **Multi-dimensional analysis**: Linguistic, domain, reasoning, temporal complexity
- **Intelligent routing**: Routes to appropriate worker based on complexity score
- **Confidence scoring**: Provides confidence in complexity assessment
- **Fallback mechanisms**: Rule-based analysis when LLM unavailable

**Complexity Categories**:
- **Simple (0.0-0.3)**: Direct fact lookups → Retriever Worker
- **Medium (0.3-0.7)**: Multi-entity queries → Enhanced Retriever Worker  
- **Complex (0.7-1.0)**: Multi-step reasoning → ReAct Worker

#### Generator (`supervisor/generator.py`)
**Purpose**: Generates final answers from retrieved context with confidence scoring.

```python
class GeneratorAgent:
    def generate_answer(
        self, 
        state: AgentState, 
        model: ChatOpenAI
    ) -> GenerationResult:
        """Generate final answer with confidence and source tracking."""
```

**Key Features**:
- **Intent-based generation**: Different prompts for different query types
- **Confidence scoring**: Quality assessment based on context and sources
- **Source extraction**: Automatic citation and source tracking
- **Execution metrics**: Token usage and generation time tracking

### Level 2: Contextualizer Layer

#### Query Understanding (`contextualizer/query_understanding.py`)
**Purpose**: Processes queries for better understanding and context integration.

```python
class QueryUnderstandingAgent:
    def process_query(
        self, 
        state: AgentState, 
        model: ChatOpenAI
    ) -> QueryUnderstandingResult:
        """Process and contextualize user query."""
```

**Processing Pipeline**:
1. **Contextualization**: Transforms queries into standalone questions
2. **Intent Classification**: Determines query type and processing needs
3. **Entity Extraction**: Identifies relevant entities and relationships
4. **Structured Query Generation**: Creates graph queries when applicable

**Example Transformation**:
```
Input:  ["Tell me about FOIA laws", "What about for journalists?"]
Output: "What are the FOIA laws specifically for journalists?"
```

### Level 3: Worker Layer

#### Retrieval Agent (`workers/retriever/retrieval.py`)
**Purpose**: Efficient document retrieval using ensemble methods.

```python
class RetrievalAgent:
    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """Retrieve documents using ensemble of retrieval methods."""
```

**Retrieval Pipeline**:
1. **Method Selection**: Choose optimal combination of retrieval methods
2. **Query Expansion**: Enhance queries using graph relationships
3. **Ensemble Retrieval**: Combine vector, keyword, and graph search
4. **Deduplication**: Remove duplicate documents
5. **Re-ranking**: Apply Cohere re-ranking for relevance
6. **Metadata Tagging**: Add tracking information

**Supported Methods**:
- **Dense (Vector)**: Semantic search using Qdrant
- **Sparse (Keyword)**: BM25 search using Elasticsearch
- **Graph**: Structured queries using Neo4j

#### ReAct Worker (`workers/react/react_worker.py`)
**Purpose**: Multi-step reasoning for complex queries.

```python
def multi_step_reasoning_agent(
    state: AgentState, 
    model: ChatOpenAI, 
    max_steps: int = 3
) -> Dict[str, Any]:
    """Perform multi-step reasoning with iterative information gathering."""
```

**Reasoning Process**:
1. **Sub-question Generation**: Break complex queries into manageable parts
2. **Iterative Retrieval**: Gather information for each sub-question
3. **Context Synthesis**: Combine information from multiple steps
4. **Final Answer**: Synthesize comprehensive response

## 🔧 Agent Implementation Patterns

### Proper Typing
All agents follow consistent typing patterns:

```python
# Input validation
validation = validate_input(query, parameters)

# Processing with error handling
try:
    result = process_with_timing()
    return create_success_result(data=result, execution_time_ms=timing)
except SpecificError as e:
    return create_error_result(error=str(e), execution_time_ms=timing)
```

### Error Handling
Structured error handling with context:

```python
try:
    # Agent processing
    pass
except AgentException:
    # Re-raise specific errors
    raise
except Exception as e:
    # Convert to structured error
    error = handle_agent_exception(e, self.agent_name, context)
    return create_error_result(error=str(error))
```

### Execution Tracking
All agents track performance metrics:

```python
start_time = time.time()
# ... processing ...
execution_time = (time.time() - start_time) * 1000

return create_success_result(
    data=result_data,
    execution_time_ms=execution_time,
    additional_metadata="value"
)
```

## 🛠️ Tools Layer

### Retrieval Tools (`tools/retrieval/`)
Specialized retrieval implementations:

- **`vector_retrieval.py`**: Qdrant vector search
- **`keyword_retrieval.py`**: Elasticsearch BM25 search  
- **`graph_retrieval.py`**: Neo4j graph queries
- **`metadata_filter.py`**: Document filtering and prioritization

### Memory Tools (`tools/memory/`)
Memory management and context handling:

- **`memory.py`**: Semantic memory with user isolation
- Context storage and retrieval
- Background memory maintenance

### Processing Tools
Document and context processing utilities:

- **`context_processor.py`**: Information extraction and citation
- **`document_formatter.py`**: Document formatting and preparation
- **`summarizer.py`**: Content summarization

## 📊 Performance Metrics

All agents provide comprehensive metrics:

### Execution Metrics
- **Processing time**: Millisecond-precision timing
- **Token usage**: LLM token consumption tracking
- **Confidence scores**: Quality assessment (0.0-1.0)

### Retrieval Metrics
- **Documents found**: Total documents before filtering
- **Documents after deduplication**: Unique documents
- **Methods used**: Which retrieval methods were employed
- **Query expansion**: Whether queries were enhanced

### Quality Metrics
- **Source citations**: Number of sources referenced
- **Context length**: Amount of context used
- **Answer length**: Generated response word count

## 🧪 Testing Patterns

### Unit Testing
```python
def test_agent_processing():
    agent = QueryUnderstandingAgent()
    state = create_test_state(query="test query")
    
    result = agent.process_query(state, mock_model)
    
    assert result.is_success
    assert result.data.contextualized_query
    assert result.execution_time_ms > 0
```

### Integration Testing
```python
def test_agent_integration():
    # Test full pipeline
    complexity_result = complexity_analyzer.analyze_complexity(query)
    understanding_result = contextualizer.process_query(state, model)
    retrieval_result = retriever.retrieve_documents(state)
    generation_result = generator.generate_answer(state, model)
    
    # Verify data flow
    assert all(r.is_success for r in [complexity_result, understanding_result, retrieval_result, generation_result])
```

### Error Testing
```python
def test_error_handling():
    with pytest.raises(QueryUnderstandingError) as exc_info:
        agent.process_query(invalid_state, model)
    
    assert exc_info.value.agent_name == "QueryUnderstanding"
    assert exc_info.value.error_category == ErrorCategory.VALIDATION
```

## 🔄 Agent Lifecycle

1. **Initialization**: Agent instances created with proper dependencies
2. **Input Validation**: Pydantic validation of input parameters
3. **Processing**: Core agent logic with error handling
4. **Metrics Collection**: Execution time and quality metrics
5. **Result Creation**: Strongly typed result objects
6. **Error Handling**: Structured exceptions with context

This architecture ensures reliable, maintainable, and scalable agent implementations with comprehensive observability and error handling.