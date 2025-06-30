# Backlog: RAG System Roadmap by Phase

This file organizes all advanced features, improvements, and experiments into clear phases for your RAG pipeline. Use this as your development roadmap!

---

## Phase 1: Ingestion & Indexing

_Goal: Get data into your vector DB in a way that maximizes future retrieval quality._

- [x] Adaptive Chunking: Use recursive, timestamp, or row-based chunking as appropriate.
- [x] Metadata Enrichment: Store all relevant metadata (source, page, timestamp, etc.) in the vector DB.
- [ ] Contextualization Prompt: (Optional, but recommended) Use an LLM to generate a short, chunk-specific context and prepend it to each chunk before embedding ([Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)).
- [ ] Chunk Size/Overlap Experiments: Experiment with different chunk sizes and overlaps for optimal retrieval.
- [ ] Unstructured.io Integration: Try Unstructured.io for more advanced chunking, especially for messy or complex docs.
- [ ] Domain-specific Prompts: Tailor contextualization prompts for your specific domain (e.g., legal, technical).
- [ ] Hierarchical Chunking (Parent-Child): Implement hierarchical chunking using parent and child splits (e.g., ParentDocumentRetriever in LangChain) to enable both broad context and pinpoint accuracy for legal documents. ([Medium guide](https://medium.com))

---

## Phase 2: Retrieval & Search

_Goal: Maximize the relevance and completeness of retrieved context for the LLM._

- [ ] BM25/Hybrid Retrieval: Combine semantic (embedding-based) and BM25 (lexical) retrieval for better recall and precision.
- [ ] Hybrid Search: Fuse results from multiple retrieval strategies (semantic, BM25, etc.).
- [ ] Graph RAG / Graph-based Retrieval: Integrate a graph database (e.g., Neo4j, Memgraph, or Qdrant's graph features) to model relationships, citations, and dependencies between documents, sections, and entities. Enable retrieval over both the vector DB and the graph DB for complex queries requiring reasoning over relationships. [LangChain Graph RAG Blog](https://blog.langchain.com/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs/)
- [ ] Hybrid Vector+Graph Retrieval: Combine semantic (vector), sparse (BM25), and graph-based retrieval. Fuse results from all three sources (vector, BM25, graph) for best recall and reasoning, especially for legal/technical domains.

  _Need implementation guidance or architecture diagrams for hybrid vector+graph retrieval? Just ask!_

- [ ] Neighbor Retrieval: When retrieving a chunk, also fetch a few chunks before and after for more context.
- [ ] Partitions: Support partitioned search (e.g., by document type, date, or topic).
- [ ] Hierarchical Search: Implement multi-level search (e.g., section, subsection, chunk).
- [ ] Entity Extraction: Extract and index entities for entity-aware retrieval.
- [ ] Recency Bias: Prefer more recent documents/chunks when relevant.
- [ ] Query Expansion & Transformation: Use LLMs to generate multiple reformulated queries (e.g., MultiQueryRetriever, HyDE) to increase recall and cover more facets of legal queries. ([LangChain docs](https://blog.langchain.com))
- [ ] Max Marginal Relevance (MMR): Enable MMR in retrievers to ensure diversity and reduce redundancy in retrieved context. ([LangChain MMR Retriever](https://blog.langchain.com))
- [ ] Metadata Filtering & Self-Querying: Use LLMs to extract structured filters from queries (e.g., jurisdiction, date, type) and apply them at retrieval time (SelfQueryRetriever in LangChain).
- [ ] Domain-Specific Embedding Models: Fine-tune or use legal-domain embedding models to improve semantic retrieval accuracy for legal texts. ([Weaviate guide](https://weaviate.io))
- [ ] In-text citation and answer provenance: Implement in-text citing and cite-while-you-answer features for QA, ensuring that answers reference their supporting sources directly in the output. [In-text Citing with LangChain QA (Medium)](https://medium.com/@yotamabraham/in-text-citing-with-langchain-question-answering-e19a24d81e39)

---

## Phase 3: Reranking & Answer Generation

_Goal: Ensure the LLM gets the best, most relevant, and most trustworthy context._

- [ ] Rerank: Integrate a reranker (e.g., Cohere, Voyage) to sort retrieved chunks by relevance to the query.
- [ ] Evaluation Framework: Set up evals to test different chunking, retrieval, and reranking strategies.
- [ ] User Feedback Loop: Allow users to flag good/bad answers to improve retrieval and chunking strategies.
- [ ] ReAct Prompt Before Answer Generation:
  - After retrieving document chunks, prompt a strong LLM (e.g., Gemma2-27B or better) to "reason-and-act" on whether each chunk is relevant to the query.
  - Extract specifics of why each chunk is relevant and tag them.
  - Generate the final answer using only the relevant, tagged chunks, and use the extracted specifics as exact citations.
  - Add a post-generation check to ensure citations are present in the answer and reduce hallucination.
- [ ] Multi-step LLM Answering: For small LLMs or complex queries, use multi-step reasoning:
  1. Reason over a small set of retrieved chunks (ideally 3, each ≤5000 characters).
  2. Synthesize an answer from the reasoning.
  3. Point to the exact text used for the answer (for citation/traceability).
- [ ] Fine-tuned LLM for Extractive Citations: Fine-tune your own LLM with a dataset of [ReAct instruction, query, retrieved docs → answer, citations] to improve extractive citation accuracy.

---

## Phase 4: Cost, Performance, and Scaling

_Goal: Make the system robust, efficient, and production-ready._

- [ ] Prompt Caching: Use prompt caching for efficient contextualization if using Anthropic/Claude.
- [ ] Better Data Ingestion: Go beyond semantic chunking—use data-specific indexing and chunking strategies based on the type of data you expect to query.
- [ ] Monitoring & Logging: Add detailed logging and monitoring for retrieval, LLM calls, and user feedback.
- [ ] Performance Optimization: Profile and optimize retrieval, chunking, and LLM inference for speed and cost.
- [ ] Partitioning & Sharding: For large-scale graph/vector DBs, implement partitioning/sharding for scalability ([see Graph RAG reference](https://ragaboutit.com/building-a-graph-rag-system-enhancing-llms-with-knowledge-graphs/)).

---

## Living Ideas & Experiments

- [ ] Retrieval Fusion: Experiment with different fusion strategies (reciprocal rank, score normalization, LLM-based fusion) for combining results from multiple retrieval methods.
- [ ] Graph Traversal Algorithms: Try BFS/DFS and Cypher/SPARQL queries for advanced graph retrieval.
- [ ] Semantic + Symbolic Reasoning: Explore combining LLMs with symbolic logic or rules for legal/technical queries.
- [ ] Graph Construction Automation: Automate the extraction of entities/relations from documents to build/expand the knowledge graph.
- [ ] UI/UX for Citations: Design UI elements that make citations, provenance, and context transparent to users.
- [ ] Feedback-Driven Retraining: Use user feedback to retrain chunking, retrieval, and answer generation models.
- [ ] Open Source Integrations: Track and test new open-source RAG, graph, and hybrid retrieval tools as they emerge.

---

## Notes on Overlaps & Conflicts

- Hybrid Search, BM25/Hybrid Retrieval, and Graph-based Retrieval are complementary; a full hybrid system should combine semantic, sparse, and graph-based retrieval for maximum recall, precision, and reasoning capability.
- Rerank and ReAct Prompt Before Answer Generation both aim to improve the quality of context passed to the LLM, but Rerank is model-agnostic, while ReAct is LLM-driven and more expensive.
- Unstructured.io Integration and Better Data Ingestion are both about improving chunking/indexing, but Unstructured.io is a tool, while "better ingestion" is a broader strategy.
- Multi-step LLM Answering and Fine-tuned LLM for Extractive Citations are both about answer quality, but the latter requires more resources and data.

---

_This file is a living document. Add new ideas and revisit after each phase!_

- [ ] Long-term memory and persistent user context: Implement a long-term memory agent using LangGraph and LangChain, enabling the system to store, retrieve, and use memories (both text and structured knowledge triples) across conversations and threads. This supports personalized, context-aware responses and persistent user knowledge. See [A Long-Term Memory Agent (LangChain Docs)](https://python.langchain.com/docs/versions/migrating_memory/long_term_memory_agent/).

- [ ] Advanced RAG retrieval and memory strategies: Explore and integrate advanced retrieval, query augmentation, and hybrid search techniques for RAG pipelines, including metadata filtering, parallel processing, and source traceability. See [RAGs📚 and Langchain- The RAG Power-Up! ⚙️ (Medium)](https://medium.com/@anixlynch/rags-and-langchain-the-rag-power-up-%EF%B8%8F-0bc9c2dbfcf3).

- [ ] Late chunking: Implement late chunking strategies where document splitting is deferred until after initial retrieval or query analysis, allowing for more context-aware and dynamic chunk boundaries. This can improve retrieval relevance and reduce context fragmentation in RAG pipelines.

- [ ] Semantic double-pass merging: Explore a two-stage retrieval process where initial chunks are merged or re-chunked based on semantic similarity or query context, enabling more coherent and contextually rich responses. Useful for reducing redundancy and improving answer quality.

- [ ] Agentic chunking: Develop agent-driven chunking methods where an LLM or agent dynamically determines chunk boundaries or selects relevant spans at retrieval time, rather than relying on static rules. This supports adaptive, task-specific chunking for complex or multi-turn queries.

- [ ] RAPTOR indexing: Integrate RAPTOR (Retrieval-Augmented Passage Transformer) indexing via LangChain to enable hierarchical, tree-based retrieval for improved multi-hop and compositional question answering in RAG pipelines.

- [ ] ColBERT indexing: Add ColBERT (Contextualized Late Interaction over BERT) indexing using LangChain, supporting dense, late-interaction retrieval for high-precision, scalable search over large corpora.

- [ ] Finetune model for RAG: Explore and implement finetuning of LLMs or retrievers specifically for your RAG use case, leveraging domain-specific data to improve retrieval relevance and answer quality.

## Reference Links: GraphRAG & Contextual Retrieval

- [Anthropic: Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — Official announcement and methodology for contextual retrieval.
- [LlamaIndex Contextual Retrieval Cookbook](https://docs.llamaindex.ai/en/stable/examples/cookbooks/contextual_retrieval/) — Practical guide and code examples for contextual retrieval.
- [Medium: GraphRAG using LangChain](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9) — Tutorial and code for building GraphRAG with LangChain.
- [LangChain Blog: Enhancing RAG-based application accuracy by constructing and leveraging knowledge graphs](https://blog.langchain.com/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs/) — Best practices for knowledge graph construction in RAG.
- [RAGAboutIt: Building a GraphRAG System from Scratch with LangChain](https://ragaboutit.com/building-a-graph-rag-system-from-scratch-with-langchain-a-comprehensive-tutorial/) — Comprehensive tutorial for GraphRAG with LangChain.

## Multi-Hop Reasoning & Advanced Retrieval (Planned)

### Motivation

- Many NEFAC use cases require reasoning over multiple hops in the knowledge graph (e.g., "Which organizations advocated for statutes cited in cases involving a specific person?").
- Simple 1-hop retrieval is insufficient for questions that require traversing several relationships or aggregating information across entities.

### Planned Features

- **Multi-hop Cypher Generation:**
  - Enhance LLM prompt engineering and few-shot examples to support multi-hop Cypher queries (e.g., 2-3 hops, aggregation, filtering).
  - Example: "Find all statutes cited in cases where Rob Bertsche was involved and the outcome was 'favorable'."
- **Path/Subgraph Extraction:**
  - Implement routines to extract shortest paths or relevant subgraphs between multiple entities (e.g., Person → Case → Statute).
  - Use fallback logic to generate and execute multiple Cypher queries for all entity pairs.
- **Graph Algorithms:**
  - Integrate Neo4j Graph Data Science algorithms (e.g., shortestPath, Personalized PageRank, node similarity) for recommendations and influence queries.
- **Hybrid Retrieval Integration:**
  - Combine graph-based multi-hop retrieval with vector and keyword retrievers.
  - Use rerankers (e.g., CohereRerank) to select the most relevant context for the LLM.
- **Explainability:**
  - Return not just answers, but also the supporting paths/subgraphs and their provenance (metadata).

### Example Multi-Hop Query

- "Which organizations advocated for reforms in statutes that were cited in cases involving NEFAC mentors?"
  - (Person:Mentor)-[:INVOLVED_IN]->(Case)-[:CITES]->(Statute)<-[:ADVOCATES_FOR]-(Organization)

### Status

- Initial support for path extraction and fallback logic is present.
- Need to expand prompt examples, Cypher generation, and retrieval orchestration for robust multi-hop reasoning.

## Tool Calling (Planned)

### Motivation

- Enable the LLM to call external tools and APIs as part of the retrieval and reasoning process, increasing flexibility and automation.
- Tools may include: dynamic Cypher query generation, on-demand graph analytics (e.g., PageRank, node similarity), document summarization, hybrid retriever orchestration, and document preview/viewer utilities.

### Planned Features

- **Dynamic Tool Invocation:**
  - Allow the LLM to select and invoke tools (functions, APIs) for sub-tasks during a user query session.
  - Example: LLM generates a Cypher query, then calls a graph analytics tool to run Personalized PageRank, then calls a summarizer on the results.
- **Hybrid Retrieval Orchestration:**
  - Use tool-calling to combine graph, vector, and keyword retrieval, and to rerank or filter results dynamically.
- **Explainable Document Previews:**
  - Enable the LLM to call a document preview or metadata tool to show users the provenance and context of retrieved results.
- **Agentic Workflows:**
  - Support multi-step, agent-like reasoning where the LLM chains together tool calls to answer complex queries.
- **LangChain Tool-Calling Integration:**
  - Leverage LangChain's tool-calling APIs and agent frameworks for seamless integration.

### Example Use Case

- User asks: "Show me the most influential organizations in NEFAC's advocacy network and summarize their recent activities."
  - LLM calls: (1) Cypher generator → (2) PageRank tool → (3) Document retriever → (4) Summarizer tool.

### Status

- Tool-calling APIs and agentic frameworks are under evaluation for integration.
- Need to define tool interfaces, security, and orchestration logic for production use.

---
### Additional Resources

- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [LangChain: RAG from Scratch Notebooks](https://github.com/langchain-ai/rag-from-scratch/blob/main/rag_from_scratch_15_to_18.ipynb)
- [RAGAboutIt: Building a Graph RAG System](https://ragaboutit.com/building-a-graph-rag-system-enhancing-llms-with-knowledge-graphs/)
- [Medium: Introduction to RAG and Simple/Complex RAG](https://medium.com/enterprise-rag/an-introduction-to-rag-and-simple-complex-rag-9c3aa9bd017b)
- [Medium: The Ultimate Guide to Agentic RAG](https://pawan-kumar94.medium.com/the-ultimate-guide-to-agentic-rag-e3cc1e94804e)