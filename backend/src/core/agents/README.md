# Hierarchical Multi-Agent System Architecture

This directory contains the hierarchical multi-agent system organized in a top-down structure that reflects the documented architecture.

## Directory Structure

```
agents/
├── __init__.py                 # Top-level imports
├── supervisor/                 # Top-level decision making
│   ├── __init__.py
│   └── complexity_analyzer.py  # Query complexity analysis
├── contextualizer/             # Query rewriting layer
│   └── __init__.py
├── workers/                    # Specialized processing agents
│   ├── __init__.py
│   ├── react/                  # ReAct reasoning worker
│   │   ├── __init__.py
│   │   └── react_worker.py
│   └── retriever/              # Simple retrieval worker
│       ├── __init__.py
│       └── retrieval.py
├── tools/                      # Foundational tools
│   ├── __init__.py
│   ├── retrieval/              # Document retrieval tools
│   │   ├── __init__.py
│   │   ├── retrieval_tools.py  # Main retrieval orchestration
│   │   ├── graph_retriever.py  # Graph database retrieval
│   │   ├── vector_retrieval.py # Vector/semantic search
│   │   ├── keyword_retrieval.py# Keyword/sparse search
│   │   └── graph_retrieval.py  # Graph query processing
│   └── memory/                 # Memory management tools
│       └── __init__.py
├── utils/                      # Common utilities
│   ├── __init__.py
│   └── state_manager.py        # State management
└── legacy/                     # Original pipeline components
    ├── __init__.py
    ├── context_processor.py
    ├── generator.py
    ├── history_manager.py
    ├── summarizer.py
    ├── validation.py
    ├── query_understanding.py
    ├── query_transformer.py
    ├── retrieval_strategy.py
    ├── multi_step_reasoning.py
    ├── state.py
    └── graph.py
```

## Import Hierarchy

The system follows a top-down import pattern:

### Level 1: Supervisor Layer
- `supervisor.complexity_analyzer` - Query complexity analysis and routing decisions

### Level 2: Contextualizer Layer  
- `contextualizer.*` - Query rewriting and context management

### Level 3: Worker Layer
- `workers.react.react_worker` - Complex reasoning with ReAct pattern
- `workers.retriever.retrieval` - Simple document retrieval

### Level 4: Tools Layer
- `tools.retrieval.*` - Document retrieval methods
- `tools.memory.*` - Memory management utilities

### Level 5: Utils Layer
- `utils.state_manager` - State management and compatibility

### Legacy Layer
- `legacy.*` - Original pipeline components for backward compatibility

## Usage

Import from the top level for clean dependencies:

```python
# Top-level imports
from src.core.agents import (
    ComplexityAnalyzer,
    EnhancedAgentState, 
    create_react_agent_function,
    create_retrieval_tool
)

# Or specific layer imports
from src.core.agents.supervisor import ComplexityAnalyzer
from src.core.agents.workers.react import create_react_agent_function
from src.core.agents.tools.retrieval import create_retrieval_tool
```

## Architecture Benefits

1. **Clear Separation of Concerns**: Each layer has a specific responsibility
2. **Top-Down Dependencies**: Higher layers depend on lower layers, not vice versa
3. **Modular Design**: Components can be developed and tested independently
4. **Legacy Compatibility**: Original components preserved for backward compatibility
5. **Scalable Structure**: Easy to add new components at appropriate levels