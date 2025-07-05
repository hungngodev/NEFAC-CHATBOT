# Query Complexity Analysis System

The Query Complexity Analysis System is a critical component of the Supervisor Agent at Level 1 of the hierarchical architecture that intelligently assesses the computational requirements of incoming queries. This system enables efficient resource allocation by routing queries to the most appropriate processing path based on their complexity characteristics.

## Core Purpose

The complexity analyzer serves as the decision engine for intelligent routing, ensuring that:
- Simple queries receive fast, efficient processing
- Complex queries get thorough, multi-step analysis
- System resources are optimized across all query types
- User experience is maximized through appropriate response strategies

## Implementation Details

**Location:** `src/core/agents/supervisor/complexity_analyzer.py`
**Main Class:** `ComplexityAnalyzer`
**Output Model:** `QueryComplexity`

## Multi-Dimensional Analysis Framework

### 1. Linguistic Complexity Assessment

**Syntax Analysis:**
- Sentence structure complexity (simple, compound, complex)
- Clause depth and nesting levels
- Grammatical complexity indicators
- Question type classification (who, what, when, where, why, how)

**Semantic Analysis:**
- Vocabulary sophistication level
- Domain-specific terminology density
- Ambiguity and context dependency
- Implicit vs explicit information requests

**Examples:**
- Simple: "What is FOIA?" (Score: 0.1)
- Medium: "How does FOIA apply to state agencies?" (Score: 0.4)
- Complex: "Analyze the constitutional implications of FOIA exemptions in the digital age" (Score: 0.9)

### 2. Domain Complexity Assessment

**Legal Concept Density:**
- Number of legal terms and concepts
- Jurisdictional complexity (federal, state, local)
- Regulatory framework involvement
- Case law and precedent requirements

**Entity Relationship Complexity:**
- Number of entities involved
- Relationship types and dependencies
- Cross-domain connections
- Temporal relationships

**Examples:**
- Simple: "NEFAC contact information" (Score: 0.1)
- Medium: "Massachusetts public records law requirements" (Score: 0.5)
- Complex: "Interaction between federal FOIA and state sunshine laws across New England" (Score: 0.8)

### 3. Reasoning Requirements Analysis

**Cognitive Load Assessment:**
- Single-step vs multi-step reasoning
- Logical inference requirements
- Causal relationship analysis
- Comparative analysis needs

**Information Synthesis Needs:**
- Multiple source integration
- Conflicting information resolution
- Pattern recognition requirements
- Trend analysis and prediction

**Examples:**
- Simple: "When was NEFAC founded?" (Score: 0.0)
- Medium: "Compare public records laws in two states" (Score: 0.6)
- Complex: "Evaluate the effectiveness of transparency laws in promoting government accountability" (Score: 0.9)

### 4. Temporal Complexity Assessment

**Time-Based Query Characteristics:**
- Historical analysis requirements
- Trend identification needs
- Temporal relationship mapping
- Evolution and change analysis

**Chronological Complexity:**
- Single point in time vs time ranges
- Sequential event analysis
- Cause-and-effect temporal relationships
- Predictive temporal reasoning

**Examples:**
- Simple: "Current FOIA filing fee" (Score: 0.1)
- Medium: "Changes in public records laws over the past 5 years" (Score: 0.5)
- Complex: "Historical evolution of press freedom protections and future implications" (Score: 0.8)

### 5. Multi-Hop Reasoning Indicators

**Information Pathway Analysis:**
- Number of reasoning steps required
- Intermediate conclusion dependencies
- Cross-reference requirements
- Validation and verification needs

**Synthesis Complexity:**
- Multiple perspective integration
- Contradictory information handling
- Evidence weighing requirements
- Conclusion confidence assessment

## Complexity Scoring Algorithm

### Weighted Scoring Model

```python
complexity_score = (
    linguistic_weight * linguistic_score +
    domain_weight * domain_score +
    reasoning_weight * reasoning_score +
    temporal_weight * temporal_score +
    multihop_weight * multihop_score
)

# Default weights
linguistic_weight = 0.15
domain_weight = 0.25
reasoning_weight = 0.30
temporal_weight = 0.15
multihop_weight = 0.15
```

### Confidence Assessment

The system also provides a confidence score (0.0-1.0) indicating how certain it is about the complexity assessment:

**High Confidence (0.8-1.0):**
- Clear linguistic patterns
- Well-defined domain boundaries
- Obvious reasoning requirements

**Medium Confidence (0.5-0.8):**
- Some ambiguous elements
- Mixed complexity indicators
- Context-dependent interpretation

**Low Confidence (0.0-0.5):**
- Highly ambiguous queries
- Conflicting complexity signals
- Insufficient context for assessment

## Implementation Architecture

### LLM-Powered Analysis

The complexity analyzer uses a specialized LLM chain with:

**Structured Output Model:**
```python
class QueryComplexity(BaseModel):
    complexity_score: float = Field(ge=0.0, le=1.0)
    reasoning_required: bool
    multi_hop_needed: bool
    tool_usage_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

**Specialized Prompt:**
- Expert system instructions for complexity assessment
- Clear scoring criteria with examples
- Context awareness for conversation history
- Fallback strategies for edge cases

### Caching and Optimization

**Query Pattern Caching:**
- Common query patterns are cached for fast lookup
- Similar queries use cached complexity scores
- Cache invalidation based on system learning

**Performance Optimization:**
- Fast-path for obviously simple queries
- Batch processing for multiple queries
- Asynchronous processing for non-blocking analysis

## Routing Decision Matrix

### Complexity Thresholds

| Complexity Range | Route Destination | Processing Strategy |
|------------------|-------------------|-------------------|
| 0.0 - 0.3 | Enhanced Retriever Worker | Single-step retrieval |
| 0.3 - 0.7 | Legacy Pipeline Agent | Full pipeline processing |
| 0.7 - 1.0 | Enhanced ReAct Worker | Multi-step reasoning |

### Adaptive Thresholds

The system can dynamically adjust thresholds based on:
- Current system load
- Historical performance data
- User feedback and satisfaction scores
- Resource availability

### Override Mechanisms

**Manual Overrides:**
- Admin-defined routing rules
- User preference settings
- Domain-specific routing policies

**Automatic Overrides:**
- System load balancing
- Error rate thresholds
- Performance degradation detection

## Integration with Memory System

### Historical Context Integration

**Past Query Analysis:**
- User's typical query complexity patterns
- Session-specific complexity trends
- Learning from previous routing decisions

**Memory-Informed Scoring:**
- Context from previous interactions
- User expertise level assessment
- Domain familiarity indicators

### Feedback Loop Integration

**Performance Feedback:**
- Route success/failure rates
- User satisfaction scores
- Response time optimization

**Continuous Learning:**
- Pattern recognition improvement
- Threshold optimization
- Error pattern identification

## Performance Metrics and Monitoring

### Key Performance Indicators

**Accuracy Metrics:**
- Routing decision accuracy rate
- False positive/negative rates
- User satisfaction correlation

**Efficiency Metrics:**
- Analysis time per query
- Cache hit rates
- Resource utilization optimization

**System Health Metrics:**
- Complexity distribution patterns
- Threshold effectiveness
- Error rates by complexity level

### Monitoring Dashboard

**Real-Time Metrics:**
- Current complexity distribution
- Route success rates
- System performance indicators

**Historical Analysis:**
- Complexity trend analysis
- Routing effectiveness over time
- User behavior pattern evolution

## Configuration and Tuning

### Environment Variables

```bash
# Complexity thresholds
COMPLEXITY_THRESHOLD_SIMPLE=0.3
COMPLEXITY_THRESHOLD_COMPLEX=0.7

# Scoring weights
LINGUISTIC_WEIGHT=0.15
DOMAIN_WEIGHT=0.25
REASONING_WEIGHT=0.30
TEMPORAL_WEIGHT=0.15
MULTIHOP_WEIGHT=0.15

# Performance settings
ENABLE_COMPLEXITY_CACHING=true
CACHE_TTL_SECONDS=3600
MAX_ANALYSIS_TIME_MS=500
```

### A/B Testing Support

**Experimental Features:**
- Alternative scoring algorithms
- Different threshold configurations
- New complexity dimensions

**Performance Comparison:**
- Side-by-side routing effectiveness
- User experience metrics
- Resource utilization comparison

## Error Handling and Fallbacks

### Graceful Degradation

**Analysis Failure Scenarios:**
1. **LLM Timeout:** Default to medium complexity (0.5)
2. **Invalid Response:** Use pattern-based fallback
3. **System Overload:** Route to least loaded path
4. **Unknown Error:** Default to Legacy Pipeline

### Recovery Mechanisms

**Automatic Recovery:**
- Retry with simplified analysis
- Fallback to rule-based classification
- Emergency routing to stable components

**Manual Intervention:**
- Admin override capabilities
- Emergency routing rules
- System maintenance modes

## Future Enhancements

### Machine Learning Integration

**Supervised Learning:**
- Training on historical routing success data
- User feedback integration
- Performance optimization

**Unsupervised Learning:**
- Query pattern discovery
- Automatic threshold optimization
- Anomaly detection

### Advanced Features

**Multi-Language Support:**
- Language-specific complexity models
- Cross-language complexity comparison
- Cultural context integration

**Domain Adaptation:**
- Legal domain specialization
- Custom complexity models
- Industry-specific optimization

The Query Complexity Analysis System represents a sophisticated approach to intelligent query routing, enabling the Enhanced Supervisor Agent to make optimal decisions for system efficiency and user satisfaction.