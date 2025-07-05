# Hierarchical System Structure

The NEFAC chatbot backend is organized in a clean hierarchical structure that reflects the documented architecture with clear separation of concerns and top-down dependencies.

## Directory Structure

```
src/core/agents/
├── __init__.py                 # Top-level imports
├── README.md                   # Architecture documentation
├── supervisor/                 # 🎯 Level 1: Decision Making
│   ├── __init__.py
│   └── complexity_analyzer.py  # Query complexity analysis & routing
├── contextualizer/             # 🔄 Level 2: Query Processing  
│   └── __init__.py
├── workers/                    # 🤖 Level 3: Specialized Agents
│   ├── __init__.py
│   ├── react/                  # Complex reasoning worker
│   │   ├── __init__.py
│   │   └── react_worker.py
│   └── retriever/              # Simple retrieval worker
│       ├── __init__.py
│       └── retrieval.py
├── tools/                      # 🔧 Level 4: Foundational Tools
│   ├── __init__.py
│   ├── retrieval/              # Document retrieval methods
│   │   ├── __init__.py
│   │   ├── retrieval_tools.py  # Main orchestration
│   │   ├── graph_retriever.py  # Graph database access
│   │   ├── vector_retrieval.py # Semantic search
│   │   ├── keyword_retrieval.py# Keyword search
│   │   └── graph_retrieval.py  # Graph query processing
│   └── memory/                 # Memory management
│       └── __init__.py
├── utils/                      # 🛠️ Level 5: Common Utilities
│   ├── __init__.py
│   └── state_manager.py        # State management
└── legacy/                     # 📦 Backward Compatibility
    ├── __init__.py
    └── [original pipeline components]
```

## Hierarchical Layers

### Level 1: Supervisor Layer
**Location:** `supervisor/`
**Purpose:** High-level decision making and intelligent routing
**Components:**
- `complexity_analyzer.py` - Multi-dimensional query complexity analysis
- Routing decisions based on complexity scores
- Resource optimization and load balancing

### Level 2: Contextualizer Layer  
**Location:** `contextualizer/`
**Purpose:** Query processing and context management
**Components:**
- Query rewriting for self-contained queries
- Memory integration and context enhancement
- Conversation history management

### Level 3: Worker Layer
**Location:** `workers/`
**Purpose:** Specialized processing agents
**Components:**
- `react/` - Complex reasoning with ReAct pattern
- `retriever/` - Simple document retrieval
- Each worker handles specific query types optimally

### Level 4: Tools Layer
**Location:** `tools/`
**Purpose:** Foundational tools and utilities
**Components:**
- `retrieval/` - Document retrieval methods and orchestration
- `memory/` - Memory management and context handling
- Reusable components for higher layers

### Level 5: Utilities Layer
**Location:** `utils/`
**Purpose:** Common utilities and infrastructure
**Components:**
- `state_manager.py` - Unified state management
- Legacy compatibility layers
- Validation and error handling

### Legacy Layer
**Location:** `legacy/`
**Purpose:** Backward compatibility
**Components:**
- All original pipeline components
- Preserved for gradual migration
- Maintains existing functionality

## Import Hierarchy

### Top-Level Imports
```python
from src.core.agents import (
    ComplexityAnalyzer,
    EnhancedAgentState,
    create_react_agent_function,
    create_retrieval_tool
)
```

### Layer-Specific Imports
```python
# Level 1: Supervisor
from src.core.agents.supervisor import ComplexityAnalyzer

# Level 3: Workers  
from src.core.agents.workers.react import create_react_agent_function
from src.core.agents.workers.retriever import retrieval_agent

# Level 4: Tools
from src.core.agents.tools.retrieval import create_retrieval_tool
from src.core.agents.tools.retrieval import GraphRetriever

# Level 5: Utils
from src.core.agents.utils import EnhancedAgentState
```

## Dependency Flow

The system follows strict top-down dependencies:

```
Supervisor Layer (Level 1)
    ↓ depends on
Contextualizer Layer (Level 2)  
    ↓ depends on
Worker Layer (Level 3)
    ↓ depends on
Tools Layer (Level 4)
    ↓ depends on
Utils Layer (Level 5)
```

**Key Principles:**
- Higher layers can import from lower layers
- Lower layers never import from higher layers
- Each layer has a specific, well-defined responsibility
- Legacy components are isolated but accessible

## Benefits

### 1. **Clear Separation of Concerns**
- Each layer has distinct responsibilities
- Easy to understand system architecture
- Simplified debugging and maintenance

### 2. **Scalable Design**
- Easy to add new components at appropriate levels
- Modular structure supports independent development
- Clean interfaces between layers

### 3. **Professional Structure**
- Follows industry best practices
- Maintainable codebase
- Clear documentation and examples

### 4. **Backward Compatibility**
- Legacy components preserved
- Gradual migration path
- No breaking changes to existing functionality

### 5. **Import Efficiency**
- Clean import statements
- No circular dependencies
- Optimized module loading

## Usage Examples

### Adding a New Tool
```python
# Add to tools/retrieval/
class NewRetrievalMethod(BaseRetriever):
    def _get_relevant_documents(self, query: str) -> List[Document]:
        # Implementation
        pass

# Update tools/retrieval/__init__.py
from .new_retrieval_method import NewRetrievalMethod
__all__.append("NewRetrievalMethod")
```

### Adding a New Worker
```python
# Add to workers/new_worker/
def create_new_worker_function(llm, tools):
    def new_worker(state):
        # Implementation
        pass
    return new_worker

# Update workers/__init__.py  
from .new_worker import create_new_worker_function
__all__.append("create_new_worker_function")
```

This hierarchical structure provides a solid foundation for the NEFAC chatbot that can scale and evolve while maintaining clean architecture principles.