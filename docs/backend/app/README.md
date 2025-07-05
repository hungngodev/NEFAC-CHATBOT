# Application Layer Documentation

The application layer orchestrates the multi-agent system using LangGraph and provides the main entry points.

## Structure

```
backend/src/app/
├── multi_agent_app.py    # LangGraph orchestration and agent coordination
└── main.py              # Main application entry point and API
```

## Core Components

### Multi-Agent Orchestration (multi_agent_app.py)

Coordinates all agents using LangGraph's state management and conditional routing.

#### System Architecture
```python
"""
Hierarchical Multi-Agent System
Properly orchestrates existing agents following the documented architecture.
Uses enhanced agents with proper typing and dependency injection.
"""
```

**Key Features**:
- **LangGraph Integration**: State-based workflow orchestration
- **Conditional Routing**: Intelligent query routing based on complexity
- **Service Management**: Dependency injection and health monitoring
- **Error Handling**: Comprehensive error handling with fallbacks
- **Type Safety**: Full type annotations throughout

#### Graph Construction
```python
def create_multi_agent_graph() -> CompiledGraph:
    """Creates the hierarchical multi-agent graph."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("contextualizer", contextualizer_node)
    workflow.add_node("retriever_worker", retriever_worker_node)
    workflow.add_node("react_worker", react_worker_node)
    workflow.add_node("final_answer", final_answer_node)
    
    # Define conditional routing
    workflow.add_conditional_edges(
        "contextualizer",
        route_after_supervisor,
        {
            "retriever_worker": "retriever_worker",
            "react_worker": "react_worker"
        }
    )
    
    return workflow.compile(checkpointer=MemorySaver())
```

### Main Application (main.py)

Provides the main entry point and API interface.

#### API Endpoints
- **POST /query**: Process user queries
- **POST /query/stream**: Streaming query processing
- **GET /health**: System health check
- **GET /metrics**: Performance metrics

## Execution Flow

```
User Query → Supervisor → Contextualizer → [Retriever|ReAct] → Generator → Response
```

**Routing Logic**:
- **Complexity < 0.3**: Simple queries → Retriever Worker
- **Complexity 0.3-0.7**: Medium queries → Enhanced Retriever Worker  
- **Complexity > 0.7**: Complex queries → ReAct Worker

## Error Handling

- **Node-level**: Graceful degradation with fallback responses
- **Service-level**: Automatic fallback to alternative implementations
- **Graph-level**: State validation and recovery mechanisms

## Monitoring

- **Execution tracking**: Node and overall performance timing
- **Health monitoring**: Service status and agent health
- **Performance metrics**: Throughput, latency, and error rates