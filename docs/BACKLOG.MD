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
