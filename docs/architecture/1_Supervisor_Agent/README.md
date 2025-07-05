# The Supervisor Agent

The Supervisor Agent is the intelligent brain of the entire backend system, located at the top of the hierarchical architecture. It acts as a high-level manager with advanced query complexity analysis, analyzing incoming user queries and delegating them to the most appropriate worker agent based on computational efficiency and resource optimization. This ensures that the system is both efficient and effective, using the right tool for the right job while minimizing unnecessary computation.

## Core Responsibilities

- **Receives all incoming user queries** with user and session context
- **Performs intelligent query complexity analysis** using multi-dimensional assessment
- **Analyzes conversation history and memory context** for informed routing decisions
- **Makes critical routing decisions based on:**
    - Query complexity score (0.0-1.0)
    - Resource availability and system load
    - User context and conversation history
    - Reasoning requirements and multi-hop needs
- **Routes queries to optimal processing paths:**
    - Simple queries (< 0.3 complexity) to Retriever Worker
    - Medium queries (0.3-0.7 complexity) to Retriever Worker with enhanced strategies
    - Complex queries (> 0.7 complexity) to ReAct Worker
- **Provides fallback mechanisms** for error recovery and system resilience

## Implementation Details

- **Location:** `src/core/agents/supervisor/complexity_analyzer.py`
- **Node Name:** `supervisor_agent`
- **State Management:** Uses `EnhancedAgentState` with proper user/session isolation
- **Class:** `ComplexityAnalyzer`
- **Complexity Analysis:** Multi-dimensional query assessment including:
  - Linguistic complexity (sentence structure, terminology)
  - Domain complexity (legal concepts, entity relationships)
  - Reasoning requirements (multi-step, causal analysis)
  - Temporal complexity (time-based queries)
  - Multi-hop indicators (comparison, synthesis needs)
- **Decision Logic:** Advanced LLM-powered routing with structured output validation
- **Memory Integration:** Considers relevant past interactions for context-aware routing
- **Performance Monitoring:** Tracks routing decisions and optimization metrics

## Query Complexity Analysis

The Enhanced Supervisor uses a sophisticated complexity analyzer that evaluates queries across multiple dimensions:

### Complexity Scoring (0.0 - 1.0)

**Simple Queries (0.0 - 0.3):**
- Basic fact lookups: "What is FOIA?"
- Single-entity queries: "Who is the NEFAC director?"
- Definition requests: "Define public records"
- Direct factual questions: "When was NEFAC founded?"

**Medium Queries (0.3 - 0.7):**
- Comparative questions: "Compare FOIA laws in Massachusetts vs Rhode Island"
- Summary requests: "Summarize recent press freedom cases"
- Multi-entity queries: "What organizations work with NEFAC?"
- Procedural questions: "How to file a public records request?"

**Complex Queries (0.7 - 1.0):**
- Multi-step analysis: "Analyze the trend of press freedom violations over the past decade"
- Causal reasoning: "What factors led to changes in public records laws?"
- Strategic planning: "Develop a strategy for challenging records denials"
- Cross-domain synthesis: "How do federal and state laws interact in records access?"

## Intelligent Prompt Engineering

The Supervisor uses a sophisticated prompt that includes:

### Context Awareness
- **Role Definition:** "You are an intelligent supervisor for a legal information system..."
- **Complexity Guidelines:** Clear criteria for routing decisions with examples
- **Resource Optimization:** Instructions to minimize computational overhead
- **Memory Integration:** Consideration of past interaction patterns

### Routing Criteria
- **Retriever Route:** For straightforward information retrieval
- **Enhanced Retriever Route:** For medium complexity queries requiring multiple strategies
- **ReAct Worker Route:** For complex reasoning and multi-step analysis
- **Error Handling:** Fallback strategies for edge cases

### Structured Output
The supervisor uses `SupervisorDecision` model with:
- `next_action`: Routing decision
- `reasoning`: Explanation of the decision
- `confidence`: Confidence score (0.0-1.0)

## Performance Optimizations

### Resource-Aware Routing
- **System Load Monitoring:** Adjusts routing based on current system capacity
- **Cost-Benefit Analysis:** Weighs processing cost against expected quality improvement
- **Early Exit Strategies:** Identifies when simple processing will suffice

### Adaptive Thresholds
- **Dynamic Adjustment:** Complexity thresholds adapt based on system performance
- **User Patterns:** Learns from user interaction patterns for better routing
- **Feedback Integration:** Incorporates validation results to improve future decisions

## Integration with Memory System

### Memory-Informed Routing
- **Context Retrieval:** Accesses relevant past interactions before routing
- **Pattern Recognition:** Identifies recurring query patterns for optimization
- **User Profiling:** Considers user expertise level and preferences
- **Session Continuity:** Maintains context across conversation turns

### Memory Storage
- **Decision Tracking:** Records routing decisions for analysis and improvement
- **Performance Metrics:** Stores timing and quality metrics for each route
- **Error Patterns:** Tracks failures for system improvement

## Error Handling and Resilience

### Fallback Mechanisms
1. **Primary Route Failure:** Automatic fallback to Legacy Pipeline
2. **Complexity Analysis Failure:** Default to medium complexity routing
3. **Memory System Failure:** Continue with basic routing without memory context
4. **Complete System Failure:** Graceful degradation with error messaging

### Monitoring and Alerting
- **Route Success Rates:** Tracks success/failure by routing decision
- **Performance Metrics:** Monitors response times and quality scores
- **Error Logging:** Comprehensive error tracking for debugging
- **Health Checks:** Regular system health validation

## Configuration Options

### Environment Variables
```bash
# Complexity thresholds
COMPLEXITY_THRESHOLD_SIMPLE=0.3
COMPLEXITY_THRESHOLD_COMPLEX=0.7

# Resource management
MAX_CONCURRENT_COMPLEX_QUERIES=5
ENABLE_ADAPTIVE_ROUTING=true

# Memory integration
ENABLE_MEMORY_ROUTING=true
MEMORY_CONTEXT_WEIGHT=0.3
```

### Runtime Configuration
- **A/B Testing:** Support for experimental routing strategies
- **Feature Flags:** Enable/disable specific routing features
- **Performance Tuning:** Adjustable parameters for optimization

## Metrics and Analytics

### Key Performance Indicators
- **Route Distribution:** Percentage of queries by complexity level
- **Response Time by Route:** Average processing time for each path
- **Accuracy by Route:** Quality scores for different routing decisions
- **Resource Utilization:** Computational cost optimization metrics

### Continuous Improvement
- **Machine Learning Integration:** Potential for ML-based routing optimization
- **User Feedback Integration:** Incorporation of user satisfaction scores
- **System Learning:** Adaptive improvement based on historical performance

The Enhanced Supervisor Agent represents a significant advancement in intelligent query routing, providing the foundation for an efficient, scalable, and user-focused multi-agent system.