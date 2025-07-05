
# The Retrieval Tools

The Retrieval Tools are the foundational components at Level 4 of the hierarchical architecture, providing specialized retrieval capabilities for different types of queries and data sources. These tools work together through intelligent orchestration to deliver comprehensive and accurate search results across vector, keyword, and graph-based retrieval methods.

## Implementation Structure

**Location:** `src/core/agents/tools/retrieval/`

### Main Components:
- `retrieval_tools.py` - Main orchestration and intelligent tool selection
- `vector_retrieval.py` - Semantic vector search using Qdrant
- `keyword_retrieval.py` - Keyword search using Elasticsearch (BM25)
- `graph_retrieval.py` - Graph query processing using Neo4j
- `graph_retriever.py` - Graph database retrieval wrapper for ensemble integration
- `metadata_filter.py` - Advanced metadata filtering and query refinement

## 1. Vector Search (Semantic Retrieval)

- **Location:** `src/core/agents/tools/retrieval/vector_retrieval.py`
- **Function:** `get_qdrant_retriever`
- **Backend:** Qdrant Vector Database
- **Purpose:** Semantic and conceptual search

Vector search excels at finding documents that are **conceptually related** to a query, even if they don't share the same keywords. It uses dense embeddings to capture semantic meaning and find the most relevant documents based on conceptual similarity.

**Key Features:**
- Dense embedding-based similarity search
- Semantic understanding beyond keyword matching
- Configurable similarity thresholds
- Integration with metadata filtering

**Optimal Use Cases:**
- Broad, conceptual questions where exact terminology isn't known
- Finding documents with similar themes using different language
- Discovering related concepts and cross-references

## 2. Keyword Search (Lexical Retrieval)

- **Location:** `src/core/agents/tools/retrieval/keyword_retrieval.py`
- **Function:** `get_bm25_retriever`
- **Backend:** Elasticsearch with BM25 scoring
- **Purpose:** Precise lexical and term-based search

Keyword search uses traditional information retrieval techniques to find documents containing **exact keywords** and phrases from the query. It employs BM25 scoring for optimal term frequency and document length normalization.

**Key Features:**
- BM25 scoring algorithm for relevance ranking
- Exact term and phrase matching
- Boolean query support
- Fast retrieval for specific terminology

**Optimal Use Cases:**
- Specific factual queries requiring precise terminology
- Searches for exact names, legal terms, or technical phrases
- Queries where keyword precision is more important than semantic similarity

## 3. Graph Search (Structured Retrieval)

- **Location:** `src/core/agents/tools/retrieval/graph_retrieval.py`
- **Function:** `graph_retrieval_agent`
- **Wrapper Class:** `GraphRetriever` (in `graph_retriever.py`)
- **Backend:** Neo4j Knowledge Graph
- **Purpose:** Structured data and relationship discovery

Graph search specializes in finding **relationships, connections, and structured information** within the knowledge graph. It uses multiple sophisticated strategies with intelligent fallback mechanisms to ensure comprehensive results.

**Retrieval Strategies (with fallbacks):**
1. **LLM-Powered QA:** Direct question answering using `GraphCypherQAChain`
2. **Generated Cypher Queries:** LLM-generated Cypher for complex structured queries
3. **Path Discovery:** Automatic `shortestPath` queries between identified entities
4. **Neighborhood Exploration:** 1-hop relationship discovery as final fallback

**Key Features:**
- Multi-strategy approach with intelligent fallbacks
- Entity recognition and canonicalization
- Relationship path discovery
- Structured query generation

**Optimal Use Cases:**
- Relationship queries: "Who is the author of case X?"
- Connection discovery: "What organizations are related to NEFAC?"
- Aggregation queries: "How many cases are related to FOIA?"
- Entity-centric information gathering
