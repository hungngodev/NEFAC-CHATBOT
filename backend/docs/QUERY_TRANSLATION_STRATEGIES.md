# Advanced Query Translation Strategies

## Overview

The NEFAC chatbot implements 8 sophisticated query translation strategies that transform user queries into optimized forms for enhanced retrieval. These techniques are based on cutting-edge research and represent state-of-the-art approaches to query optimization.

## Strategy Implementations

### 1. RAG Fusion (`rag_fusion.py`)

**Concept**: Generate multiple query variations and use Reciprocal Rank Fusion to combine results.

```python
def reciprocal_rank_fusion(results: list[list], k=60) -> Any:
    """Advanced ranking fusion algorithm combining multiple query results"""
    fused_scores = {}
    for docs in results:
        for rank, doc in enumerate(docs):
            doc_str = dumps(doc)
            if doc_str not in fused_scores:
                fused_scores[doc_str] = 0
            fused_scores[doc_str] += 1 / (rank + k)
    return [loads(doc) for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)]
```

**Benefits**:
- **Improved recall** through query diversification
- **Robust ranking** via mathematical fusion
- **Handles query ambiguity** effectively

### 2. HyDE - Hypothetical Document Embedding (`hyDe.py`)

**Concept**: Generate a hypothetical answer, then retrieve documents similar to that answer.

```python
def get_hyDe_chain(retriever) -> Any:
    hyde_rag_chain = (
        # Generate hypothetical document
        {"context": hyde_generation | retriever, "question": lambda x: x["question"]}
        | final_prompt
        | model
        | StrOutputParser()
    )
    return hyde_rag_chain
```

**Benefits**:
- **Bridges semantic gap** between queries and documents
- **Improves retrieval accuracy** for complex questions
- **Handles implicit information needs**

### 3. Step-back Prompting (`step_back.py`)

**Concept**: Generate broader, more abstract questions to retrieve foundational information.

```python
examples = [
    {
        "input": "Can I film police during a protest in Massachusetts?",
        "output": "What are the legal rights around recording public officials in Massachusetts?",
    },
    {
        "input": "How do I request public records from New Hampshire?", 
        "output": "What are the legal processes for obtaining public records in New Hampshire?",
    },
]
```

**Benefits**:
- **Retrieves foundational knowledge** before specific details
- **NEFAC/legal domain optimization** with curated examples
- **Improves reasoning** for complex legal questions

### 4. Multi-Query Generation (`multi_query.py`)

**Concept**: Generate multiple perspectives of the same question for comprehensive retrieval.

```python
def get_unique_union(documents: list[list]) -> Any:
    """Unique union of retrieved docs across multiple query perspectives"""
    flattened_docs = [dumps(doc) for sublist in documents for doc in sublist]
    unique_docs = list(set(flattened_docs))
    return [loads(doc) for doc in unique_docs]
```

**Benefits**:
- **Comprehensive coverage** through perspective diversity
- **Reduces retrieval bias** from single query formulation
- **Handles ambiguous queries** effectively

### 5. Contextual Strategy (`contextual_strategy.py`)

**Concept**: Transform queries based on conversation context and user intent.

**Benefits**:
- **Context-aware transformations** for better relevance
- **Maintains conversation coherence**
- **Adapts to user's information needs**

### 6. Query Decomposition (`decomposition.py`)

**Concept**: Break complex queries into simpler, more focused sub-queries.

**Benefits**:
- **Handles complex multi-part questions**
- **Improves retrieval precision** for each component
- **Enables systematic information gathering**

### 7. Factual Strategy (`factual_strategy.py`)

**Concept**: Reformulate queries to focus on factual, verifiable information.

**Benefits**:
- **Optimizes for factual retrieval**
- **Reduces hallucination risk**
- **Improves accuracy** for legal/regulatory queries

### 8. Multi-Query Perspectives (`multi_query.py`)

**Concept**: Generate queries from different analytical perspectives (legal, practical, historical).

**Benefits**:
- **Comprehensive analysis** from multiple angles
- **Enriched context** for complex legal issues
- **Balanced information retrieval**

## Integration Architecture

### Query Translation Pipeline

```python
class QueryTransformer:
    def __init__(self):
        self.strategies = {
            'rag_fusion': get_rag_fusion_chain,
            'hyde': get_hyDe_chain,
            'step_back': get_step_back_chain,
            'multi_query': get_multi_query_chain,
            # ... other strategies
        }
    
    def transform_query(self, query: str, strategy: str, retriever):
        return self.strategies[strategy](retriever)
```

### Strategy Selection Logic

The system intelligently selects appropriate strategies based on:

1. **Query Complexity**: Simple vs. complex questions
2. **Domain Context**: Legal vs. general information needs
3. **User Intent**: Factual lookup vs. analytical reasoning
4. **Historical Performance**: Success rates for similar queries

### Performance Optimization

- **Parallel Processing**: Multiple strategies can run concurrently
- **Caching**: Transformed queries cached for reuse
- **Adaptive Selection**: Strategy performance tracked and optimized
- **Fallback Mechanisms**: Graceful degradation if strategies fail

## Research Foundation

These strategies are based on recent advances in information retrieval:

- **RAG Fusion**: Combines multiple retrieval approaches mathematically
- **HyDE**: Leverages generative models for better semantic matching
- **Step-back**: Implements hierarchical reasoning patterns
- **Multi-Query**: Addresses query formulation bias

## Domain Specialization

### Legal/NEFAC Optimizations

- **Legal terminology** handling in all strategies
- **Regulatory context** awareness
- **Citation and case law** specific transformations
- **Public records** and transparency focus

### Example Transformations

```python
# Original Query
"Can I record a town meeting in Vermont?"

# RAG Fusion Variants
[
    "What are the recording rights for public meetings in Vermont?",
    "Vermont open meeting law recording provisions",
    "Legal requirements for filming government meetings Vermont"
]

# Step-back Abstraction
"What are the general principles of open meeting laws in Vermont?"

# HyDE Hypothetical Answer
"Vermont's open meeting law allows public recording of town meetings..."
```

## Future Enhancements

### Planned Improvements

1. **Dynamic Strategy Selection**: ML-based strategy optimization
2. **Domain-Specific Strategies**: Specialized transformations for different legal areas
3. **User Feedback Integration**: Learning from user interactions
4. **Real-time Adaptation**: Strategy adjustment based on retrieval success

### Advanced Features

- **Semantic Clustering**: Group similar transformed queries
- **Quality Scoring**: Rank strategy effectiveness
- **Contextual Memory**: Remember successful transformations
- **Cross-Strategy Learning**: Share insights between approaches

## Conclusion

This comprehensive query translation system represents a **state-of-the-art approach** to information retrieval optimization. By implementing multiple sophisticated strategies and intelligently selecting among them, the system achieves:

- **Superior retrieval quality** compared to single-strategy approaches
- **Robust performance** across diverse query types
- **Domain expertise** in legal and transparency contexts
- **Research-backed methodologies** with practical optimizations

The combination of these 8 strategies creates a powerful foundation for accurate, comprehensive, and contextually appropriate information retrieval in the legal domain.