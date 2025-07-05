
# The Retriever Worker

The Retriever Worker is a specialized agent at Level 3 of the hierarchical architecture, designed for **efficient and comprehensive document retrieval**. It serves as an intelligent search orchestrator that combines multiple retrieval strategies to provide optimal results for both simple and medium complexity queries.

## Core Responsibilities

- **Strategy Selection:** Intelligently chooses the best combination of retrieval methods based on query characteristics
- **Multi-Method Retrieval:** Executes vector search, keyword search, and graph retrieval in optimal combinations
- **Result Orchestration:** Aggregates results from multiple sources using ensemble techniques
- **Quality Enhancement:** Applies re-ranking and deduplication to ensure high-quality results
- **Performance Optimization:** Balances retrieval quality with response time for different complexity levels

## Implementation Details

- **Location:** `src/core/agents/workers/retriever/retrieval.py`
- **Function:** `retrieval_agent`
- **State Management:** Uses `EnhancedAgentState` with retrieval selection and query transformation
- **Strategy Selection:** Intelligent selection from available retrieval methods:
    - `dense`: Semantic vector search using Qdrant
    - `sparse`: Keyword search using Elasticsearch (BM25)
    - `graph`: Structured data retrieval using Neo4j
- **Ensemble Approach:** Uses `EnsembleRetriever` with configurable weights for optimal result combination
- **Query Enhancement:** Supports query expansion using graph relationships when applicable
- **Re-ranking:** Applies Cohere re-ranking for improved result quality
- **Deduplication:** Advanced deduplication based on content, source, and metadata

## The Power of Abstraction

The Retriever Worker is a powerful example of abstraction in this architecture. Higher-level agents, like the ReAct Worker, don't need to know about the complexities of vector search, graph search, or keyword search. They simply have access to a single, powerful `retrieval_tool` that they can call with a query. This keeps the reasoning logic of the higher-level agents clean and focused, as they can trust the Retriever Worker to handle the complexities of document retrieval.
