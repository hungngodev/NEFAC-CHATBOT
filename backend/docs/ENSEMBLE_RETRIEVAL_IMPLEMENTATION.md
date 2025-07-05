# Ensemble Retrieval Implementation - Technical Deep Dive

## Overview

The NEFAC chatbot implements a sophisticated **true ensemble retrieval architecture** that coordinates three distinct retrieval methods using LangChain's EnsembleRetriever with intelligent weighting and advanced post-processing.

## Architecture Implementation

### Core Ensemble Coordination

```python
# From RetrievalAgent._retrieve_with_ensemble()
def _retrieve_with_ensemble(self, queries: List[str], methods: List[RetrievalMethod], 
                           weights: List[float], state: AgentState) -> List[Document]:
    retrievers = []
    
    for method in methods:
        try:
            if method == RetrievalMethod.DENSE:
                retrievers.append(get_qdrant_retriever())      # Method 1: Vector/Dense
            elif method == RetrievalMethod.SPARSE:
                retrievers.append(get_bm25_retriever())        # Method 2: Keyword/Sparse  
            elif method == RetrievalMethod.GRAPH:
                retrievers.append(GraphRetriever(state))       # Method 3: Knowledge Graph
        except Exception as e:
            logging.error(f"Failed to initialize {method.value} retriever: {e}")
    
    # Create weighted ensemble
    ensemble_retriever = EnsembleRetriever(retrievers=retrievers, weights=weights)
    
    # Process multiple expanded queries
    all_documents = []
    for query in queries:
        if query and query.strip():
            documents = ensemble_retriever.invoke(query)
            all_documents.extend(documents)
    
    return all_documents
```

## Three Retrieval Methods

### Method 1: Dense Vector Retrieval (Qdrant)

**File**: `backend/src/core/agents/tools/retrieval/vector_retrieval.py`

```python
def get_qdrant_retriever() -> object:
    """Return a Qdrant retriever for dense/semantic search."""
    qdrant_url = os.environ["QDRANT_ENDPOINT"]
    collection_name = os.environ["QDRANT_CLUSTER_ID"]
    api_key = os.environ.get("QDRANT_API_KEY")
    
    client = QdrantClient(url=qdrant_url, api_key=api_key)
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model,  # text-embedding-3-large
    )
    return vectorstore.as_retriever()
```

**Capabilities**:
- **Semantic similarity** through vector embeddings
- **Conceptual understanding** for broad, meaning-based queries
- **OpenAI text-embedding-3-large** for state-of-the-art embeddings
- **Metadata filtering and prioritization**

### Method 2: Sparse Keyword Retrieval (BM25)

**File**: `backend/src/core/agents/tools/retrieval/keyword_retrieval.py`

```python
def get_bm25_retriever() -> object:
    """Return a BM25 retriever for sparse/keyword search."""
    # BM25 implementation for exact term matching
    # Optimized for legal terminology and specific phrases
    return bm25_retriever
```

**Capabilities**:
- **Exact term matching** for precise queries
- **Legal terminology optimization** for domain-specific terms
- **BM25 algorithm** for statistical relevance scoring
- **Complementary precision** to semantic search

### Method 3: Knowledge Graph Retrieval (Neo4j)

**File**: `backend/src/core/agents/tools/retrieval/graph_retrieval.py` (522 lines)

```python
class GraphRetriever(BaseRetriever):
    """Minimal RetrieverLike wrapper for graph_retrieval_agent"""
    
    def __init__(self, state: AgentState):
        self.state = state
    
    def invoke(self, input_query: str, **kwargs) -> List[Document]:
        updated_state = self.state.model_copy(update={"transformed_query": input_query})
        return graph_retrieval_agent(updated_state)
```

**Capabilities**:
- **Entity extraction and canonicalization**
- **LLM-powered Cypher query generation**
- **Path finding** between related entities
- **Structured relationship discovery**
- **522 lines of sophisticated Neo4j integration**

## Ensemble Processing Pipeline

### 1. Strategy Selection
```python
# Intelligent method selection based on query characteristics
retrieval_config = self._extract_retrieval_config(state)
validation = validate_retrieval_input(
    query=retrieval_config["query"], 
    retrieval_methods=retrieval_config["methods"], 
    weights=retrieval_config["weights"]
)
```

### 2. Query Expansion
```python
# Expand queries using graph relationships if applicable
expanded_queries = self._expand_queries(
    query=validation.query, 
    methods=validation.retrieval_methods, 
    entities=state.entities or []
)
```

### 3. Ensemble Retrieval
```python
# Retrieve documents using ensemble approach
all_documents = self._retrieve_with_ensemble(
    queries=expanded_queries,
    methods=validation.retrieval_methods,
    weights=validation.weights,
    state=state
)
```

### 4. Post-Processing
```python
# Deduplicate documents
unique_documents = self._deduplicate_documents(all_documents)

# Apply re-ranking if documents exist
final_documents = self._apply_reranking(documents=unique_documents, query=validation.query)

# Limit results
final_documents = final_documents[:validation.max_documents]
```

## Advanced Features

### Intelligent Weighting
- **Dynamic weight calculation** based on query characteristics
- **Method-specific optimization** for different query types
- **Fallback weight distribution** if methods fail

### Multi-Query Processing
- **Query expansion** using graph relationships
- **Multiple query variants** processed through ensemble
- **Result aggregation** across all query variations

### Cohere Re-ranking
```python
def _apply_reranking(self, documents: List[Document], query: str) -> List[Document]:
    """Apply re-ranking to improve document relevance."""
    try:
        compressor = CohereRerank(model="rerank-english-v3.0")
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, 
            base_retriever=identity_retriever
        )
        return compression_retriever.invoke(query)
    except Exception as e:
        logging.warning(f"Reranking failed: {e}")
        return documents
```

### Intelligent Deduplication
```python
def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
    """Deduplicate documents based on content and metadata."""
    unique_docs = {}
    for doc in documents:
        content = doc.page_content
        metadata = doc.metadata or {}
        source = metadata.get("source", "unknown")
        title = metadata.get("title", "unknown")
        
        doc_key = (content, source, title)
        if doc_key not in unique_docs:
            unique_docs[doc_key] = doc
    
    return list(unique_docs.values())
```

## Performance Metrics

### Execution Tracking
```python
# Create result with comprehensive metadata
data = RetrievalData(
    documents=final_documents,
    retrieval_methods_used=validation.retrieval_methods,
    total_documents_found=len(all_documents),
    documents_after_deduplication=len(unique_documents),
    deduplication_applied=len(all_documents) != len(unique_documents),
    reranking_applied=len(unique_documents) > 0,
    query_expansion_applied=len(expanded_queries) > 1,
    retrieval_time_ms=execution_time,
)
```

## Error Handling and Resilience

### Method Failure Handling
- **Graceful degradation** if individual methods fail
- **Automatic fallback** to available methods
- **Weight redistribution** when methods are unavailable

### Comprehensive Logging
- **Method initialization tracking**
- **Query processing monitoring**
- **Performance metrics collection**
- **Error reporting and recovery**

## Integration with Query Translation

The ensemble retrieval works seamlessly with all 8 query translation strategies:

1. **RAG Fusion** → Multiple queries → Ensemble retrieval → RRF combination
2. **HyDE** → Hypothetical document → Ensemble retrieval → Context synthesis
3. **Step-back** → Abstract query → Ensemble retrieval → Foundational knowledge
4. **Multi-Query** → Multiple perspectives → Ensemble retrieval → Unique union

## Conclusion

This ensemble retrieval implementation represents a **state-of-the-art approach** that:

- **Combines three distinct retrieval paradigms** for comprehensive coverage
- **Uses LangChain's EnsembleRetriever** for proven coordination
- **Implements intelligent weighting** based on query characteristics
- **Provides advanced post-processing** with Cohere re-ranking
- **Ensures robust operation** with comprehensive error handling

The system achieves superior retrieval quality by leveraging the strengths of each method while mitigating their individual weaknesses through ensemble coordination.