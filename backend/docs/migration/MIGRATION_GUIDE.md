# Migration Guide: Enhanced Multi-Agent System

This guide explains how to migrate from the current linear RAG pipeline to the enhanced hierarchical multi-agent system.

## Overview of Changes

### Before (Current server.py)

- Linear pipeline: history_manager → query_understanding → retrieval_strategy → ... → validation
- Single AgentState with 15+ fields
- No intelligent routing
- Basic memory management (truncation only)
- Every query goes through full pipeline

### After (Enhanced System)

- Hierarchical routing: supervisor → [retriever_worker | react_agent | pipeline_agent] → final_answer
- Clean EnhancedAgentState with proper separation
- Intelligent complexity-based routing
- Semantic memory with user isolation
- Efficient resource usage

## Migration Steps

### 1. Update Imports

Replace imports in your application:

```python
# OLD
from src.core.agents.main import ask_llm_stream_agentic
from src.app.server import app

# NEW
from src.app.enhanced_main import ask_llm_stream_enhanced, ask_llm_enhanced
from src.app.enhanced_server import app  # Enhanced graph
```

### 2. Update Function Calls

#### Streaming Interface

```python
# OLD
async for chunk in ask_llm_stream_agentic(query, convo_id):
    yield chunk

# NEW
async for chunk in ask_llm_stream_enhanced(
    query=query,
    convo_id=convo_id,
    user_id=user_id,  # New: user isolation
    session_id=session_id  # New: session management
):
    yield chunk
```

#### Non-Streaming Interface

```python
# OLD
# No direct non-streaming interface

# NEW
result = ask_llm_enhanced(
    query=query,
    convo_id=convo_id,
    user_id=user_id,
    session_id=session_id
)
answer = result["answer"]
```

### 3. Update State Management

#### Creating State

```python
# OLD
from src.schemas.state import AgentState
state = AgentState(
    query=query,
    chat_history=[HumanMessage(content=query)]
)

# NEW
from src.core.agents.enhanced_state import create_enhanced_state
state = create_enhanced_state(
    user_query=query,
    user_id=user_id,
    session_id=session_id
)
```

#### Using Legacy Agents with Enhanced State

```python
# OLD
result = some_agent(legacy_state)

# NEW
from src.core.agents.enhanced_state import StateManager
legacy_state = StateManager.prepare_for_legacy_agent(enhanced_state, "agent_name")
result = some_agent(legacy_state)
StateManager.update_from_legacy_result(enhanced_state, result, "agent_name")
```

### 4. Memory System Integration

#### Storing Interactions

```python
# OLD
# No persistent memory

# NEW
from src.core.memory.enhanced_memory import global_memory_manager

await global_memory_manager.store_interaction(
    user_id=user_id,
    session_id=session_id,
    query=query,
    response=response,
    metadata={"complexity": 0.7, "route": "react"}
)
```

#### Retrieving Memories

```python
# NEW
memories = await global_memory_manager.retrieve_relevant_memories(
    user_id=user_id,
    session_id=session_id,
    query=current_query,
    k=5
)
```

### 5. Configuration Updates

#### Environment Variables

Add to your .env file:

```bash
# Memory Configuration
MEMORY_BACKEND=memory  # or "qdrant" or "chroma"
MEMORY_RETENTION_DAYS=30
MAX_MEMORIES_PER_SESSION=100

# Enhanced Features
ENABLE_COMPLEXITY_ROUTING=true
ENABLE_SEMANTIC_MEMORY=true
RELEVANCE_THRESHOLD=0.7
```

#### LangGraph Configuration

```python
# OLD
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# NEW (Enhanced)
memory = MemorySaver()
app = workflow.compile(
    checkpointer=memory,
    interrupt_before=None,  # Can add human-in-the-loop
    interrupt_after=None
)
```

## Backward Compatibility

The enhanced system maintains backward compatibility:

### 1. Legacy Agent Integration

All existing agents work with the enhanced system through wrapper functions:

```python
from src.core.agents.enhanced_state import create_legacy_agent_wrapper

# Wrap legacy agents
wrapped_agent = create_legacy_agent_wrapper(original_agent, "agent_name")
```

### 2. Existing API Compatibility

The streaming interface maintains the same format:

```python
# This still works
async for chunk in ask_llm_stream_agentic(query, convo_id):
    yield chunk
```

### 3. State Conversion

Convert between state formats as needed:

```python
# Enhanced to Legacy
legacy_state = enhanced_state.to_legacy_state()

# Legacy to Enhanced
enhanced_state = EnhancedAgentState.from_legacy_state(legacy_state)
```

## Performance Improvements

### 1. Intelligent Routing

- Simple queries (complexity < 0.3): Direct retrieval
- Medium queries (0.3-0.7): Enhanced retrieval or existing pipeline
- Complex queries (> 0.7): ReAct reasoning

### 2. Early Exit

- Queries can exit early when sufficient information is found
- No unnecessary processing for simple questions

### 3. Memory Efficiency

- Semantic memory reduces redundant processing
- User isolation prevents cross-contamination

## Testing Migration

### 1. Gradual Migration

```python
# Use feature flags for gradual rollout
USE_ENHANCED_SYSTEM = os.getenv("USE_ENHANCED_SYSTEM", "false").lower() == "true"

if USE_ENHANCED_SYSTEM:
    from src.app.enhanced_main import ask_llm_stream_enhanced as stream_func
else:
    from src.core.agents.main import ask_llm_stream_agentic as stream_func
```

### 2. A/B Testing

```python
import random

def get_stream_function(user_id: str):
    # Route 50% of users to enhanced system
    if hash(user_id) % 2 == 0:
        return ask_llm_stream_enhanced
    else:
        return ask_llm_stream_agentic
```

### 3. Health Monitoring

```python
from src.app.enhanced_main import health_check

# Regular health checks
health_status = await health_check()
if health_status["status"] != "healthy":
    # Fallback to legacy system
    pass
```

## Troubleshooting

### Common Issues

#### 1. State Conversion Errors

```python
# Ensure proper state initialization
try:
    enhanced_state = create_enhanced_state(query, user_id, session_id)
except Exception as e:
    # Fallback to legacy state
    legacy_state = AgentState(query=query, chat_history=[HumanMessage(content=query)])
```

#### 2. Memory Backend Issues

```python
# Fallback to in-memory if vector store fails
try:
    from src.core.memory.enhanced_memory import create_memory_manager
    memory_manager = create_memory_manager("qdrant")
except Exception:
    memory_manager = create_memory_manager("memory")  # Fallback
```

#### 3. Agent Compatibility

```python
# Wrap legacy agents that don't work with enhanced state
from src.core.agents.enhanced_state import create_legacy_agent_wrapper

try:
    result = enhanced_agent(enhanced_state)
except Exception:
    wrapped_agent = create_legacy_agent_wrapper(legacy_agent, "agent_name")
    result = wrapped_agent(enhanced_state)
```

## Rollback Plan

If issues arise, you can quickly rollback:

### 1. Environment Variable Rollback

```bash
# Set in .env
USE_ENHANCED_SYSTEM=false
```

### 2. Import Rollback

```python
# Change imports back to original
from src.core.agents.main import ask_llm_stream_agentic
from src.app.server import app
```

### 3. Database Rollback

```python
# Enhanced memory is additive, so no data loss
# Simply stop using enhanced memory manager
```

## Monitoring and Metrics

### 1. Performance Metrics

```python
# Track routing decisions
routing_metrics = {
    "simple_queries": 0,
    "medium_queries": 0,
    "complex_queries": 0
}

# Track response times
response_times = {
    "retriever_worker": [],
    "react_agent": [],
    "pipeline_agent": []
}
```

### 2. Memory Metrics

```python
# Monitor memory usage
memory_stats = global_memory_manager.get_stats()
print(f"Total stored: {memory_stats['total_stored']}")
print(f"Total searches: {memory_stats['total_searches']}")
```

### 3. Error Tracking

```python
# Track errors by component
error_counts = {
    "supervisor": 0,
    "contextualizer": 0,
    "retriever_worker": 0,
    "react_agent": 0,
    "memory": 0
}
```

## Next Steps

1. **Phase 1**: Deploy enhanced system alongside existing system
2. **Phase 2**: Route 10% of traffic to enhanced system
3. **Phase 3**: Gradually increase traffic based on performance
4. **Phase 4**: Full migration once stable
5. **Phase 5**: Remove legacy code

## Support

For issues during migration:

1. Check the health_check() output
2. Review logs for specific error messages
3. Use backward compatibility features
4. Implement gradual rollout with feature flags
