"""
Retrieval Tools Architecture
Clean separation of concerns with intelligent method selection and aggregation.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever

from src.core.agents.tools.retrieval.graph_retrieval import get_graph_retriever
from src.core.agents.tools.retrieval.keyword_retrieval import get_bm25_retriever
from src.core.agents.tools.retrieval.vector_retrieval import get_qdrant_retriever
from src.schemas.retrieval import RetrievalStrategy

logger = logging.getLogger(__name__)


class RetrievalWorker:
    """
    Retrieval worker focused on method selection and aggregation.
    Clean separation from complex query transformation logic.
    """

    def __init__(self, llm=None):
        self.llm = llm
        self.available_methods = {"dense": "Semantic/vector search using embeddings", "sparse": "Keyword-based search using BM25", "graph": "Structured knowledge graph search"}

    def select_retrieval_strategy(self, input: str, context: Optional[Dict[str, Any]] = None) -> RetrievalStrategy:
        """Intelligently select retrieval methods based on query characteristics."""

        if self.llm:
            return self._llm_strategy_selection(input, context)
        else:
            return self._rule_based_strategy_selection(input, context)

    def _llm_strategy_selection(self, input: str, context: Optional[Dict[str, Any]] = None) -> RetrievalStrategy:
        """Use LLM for intelligent strategy selection."""

        strategy_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at selecting optimal retrieval strategies for legal queries.

Available methods:
- dense: Semantic/vector search - best for conceptual queries, synonyms, related topics
- sparse: Keyword search (BM25) - best for exact terms, names, specific phrases
- graph: Knowledge graph search - best for relationships, entities, structured data

Guidelines:
- Use dense for broad, conceptual queries
- Use sparse for specific terms, names, citations
- Use graph for entity relationships, structured queries
- Combine methods for complex queries
- Weight methods based on query characteristics

Consider query complexity, entity presence, and conceptual vs factual nature.""",
                ),
                ("human", "Query: {query}\nContext: {context}\n\nSelect optimal retrieval strategy."),
            ]
        )

        try:
            chain = strategy_prompt | self.llm.with_structured_output(RetrievalStrategy)
            result = chain.invoke({"query": input, "context": str(context) if context else ""})
            return result
        except Exception:
            return self._rule_based_strategy_selection(input, context)

    def _rule_based_strategy_selection(self, input: str, context: Optional[Dict[str, Any]] = None) -> RetrievalStrategy:
        """Rule-based fallback strategy selection."""

        query_lower = input.lower()
        methods = []
        weights = []
        reasoning_parts = []

        # Define query patterns
        entity_patterns = ["who is", "what is", "relationship", "connected", "related to", "organization", "person", "case", "statute"]
        exact_term_patterns = ["foia", "public records", "sunshine law", "exemption", "massachusetts", "rhode island", "connecticut"]
        concept_patterns = ["similar", "like", "about", "regarding", "concerning", "concept", "principle", "approach", "method"]

        # Check for different query types
        has_entities = any(pattern in query_lower for pattern in entity_patterns)
        has_exact_terms = any(pattern in query_lower for pattern in exact_term_patterns) or '"' in input
        has_concepts = any(pattern in query_lower for pattern in concept_patterns)

        # Default to dense for general queries
        if not (has_entities or has_exact_terms or has_concepts):
            has_concepts = True

        # Build strategy with equal weights for selected methods
        base_weight = 0.4
        if has_entities:
            methods.append("graph")
            weights.append(base_weight)
            reasoning_parts.append("graph search for entity relationships")

        if has_exact_terms:
            methods.append("sparse")
            weights.append(base_weight)
            reasoning_parts.append("keyword search for exact terms")

        if has_concepts:
            methods.append("dense")
            weights.append(base_weight)
            reasoning_parts.append("semantic search for conceptual understanding")

        # Normalize weights and handle fallback
        if methods and weights:
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            reasoning = f"Selected {', '.join(methods)} based on: {', '.join(reasoning_parts)}"
        else:
            # Fallback to dense search
            methods = ["dense"]
            weights = [1.0]
            reasoning = "Default semantic search"

        return RetrievalStrategy(methods=methods, weights=weights, reasoning=reasoning, query_expansion=len(methods) > 1, rerank=True)

    def create_ensemble_retriever(self, strategy: RetrievalStrategy, state: Dict[str, Any]) -> EnsembleRetriever:
        """Create ensemble retriever based on strategy."""

        retrievers = []

        for method in strategy.methods:
            try:
                if method == "dense":
                    retrievers.append(get_qdrant_retriever())
                elif method == "sparse":
                    retrievers.append(get_bm25_retriever())
                elif method == "graph":
                    retrievers.append(get_graph_retriever(state))
            except Exception as e:
                logger.warning(f"Failed to initialize {method} retriever: {e}")
                continue

        # Fallback if no retrievers
        if not retrievers:
            try:
                retrievers = [get_qdrant_retriever()]
                strategy.weights = [1.0]
            except Exception as e:
                logger.error(f"Failed to create fallback retriever: {e}")
                raise

        # Ensure weights match retrievers
        if len(strategy.weights) != len(retrievers):
            strategy.weights = [1.0 / len(retrievers)] * len(retrievers)

        return EnsembleRetriever(retrievers=retrievers, weights=strategy.weights)

    def apply_reranking(self, documents: List[Document], input: str) -> List[Document]:
        """Apply reranking to improve result quality."""

        if not documents:
            return documents

        try:
            compressor = CohereRerank(model="rerank-english-v3.0")

            class IdentityRetriever(BaseRetriever):
                def _get_relevant_documents(self, input: str, **kwargs) -> List[Document]:
                    return documents

                def invoke(self, input: str, **kwargs) -> List[Document]:
                    return documents

            identity_retriever = IdentityRetriever()
            compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=identity_retriever)

            return compression_retriever.invoke(input)

        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return documents

    def deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """Remove duplicate documents based on content and metadata."""
        if not documents:
            return documents

        unique_docs = {}

        for doc in documents:
            # Create unique key from content and source
            content = doc.page_content[:500]  # Use first 500 chars for key to avoid memory issues
            metadata = doc.metadata or {}
            source = metadata.get("source", "unknown")
            title = metadata.get("title", "")

            key = (content, source, title)

            # Keep first occurrence or higher quality version
            if key not in unique_docs:
                unique_docs[key] = doc
            else:
                # Prefer documents with more metadata
                existing_meta_count = len(unique_docs[key].metadata or {})
                new_meta_count = len(metadata)
                if new_meta_count > existing_meta_count:
                    unique_docs[key] = doc

        return list(unique_docs.values())

    def retrieve_documents(self, input: str, state: Dict[str, Any], max_docs: int = 10) -> List[Document]:
        """Main retrieval method - orchestrates the entire process."""

        try:
            # 1. Select retrieval strategy
            strategy = self.select_retrieval_strategy(input, state)

            # 2. Create ensemble retriever
            ensemble_retriever = self.create_ensemble_retriever(strategy, state)

            # 3. Retrieve documents
            documents = ensemble_retriever.invoke(input)

            # 4. Deduplicate
            documents = self.deduplicate_documents(documents)

            # 5. Apply reranking if requested
            if strategy.rerank and documents:
                documents = self.apply_reranking(documents, input)

            # 6. Limit results
            documents = documents[:max_docs]

            # 7. Add metadata
            for i, doc in enumerate(documents):
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update({"retrieval_strategy": strategy.methods, "retrieval_rank": i + 1, "stream_tag": "retrieved_docs"})

            return documents

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []


def create_retrieval_tool(llm=None):
    """Factory function to create a retrieval tool."""

    worker = RetrievalWorker(llm)

    def retrieval_tool(input: str, state: Dict[str, Any]) -> str:
        """Retrieval tool with clean interface."""

        try:
            documents = worker.retrieve_documents(input, state)

            if not documents:
                return "No relevant documents found for this query."

            # Format results
            doc_summaries = []
            for i, doc in enumerate(documents[:5]):  # Top 5 docs
                content = doc.page_content[:200]
                source = doc.metadata.get("source", "Unknown") if doc.metadata else "Unknown"
                doc_summaries.append(f"Doc {i+1}: {content}... (Source: {source})")

            return f"Retrieved {len(documents)} documents:\n" + "\n".join(doc_summaries)

        except Exception as e:
            return f"Retrieval error: {str(e)}"

    return retrieval_tool


def create_retriever_worker_function(llm=None):
    """Factory function to create a retriever worker function."""

    worker = RetrievalWorker(llm)

    def retriever_worker(state: Dict[str, Any]) -> Dict[str, Any]:
        """Retriever worker for direct queries."""

        try:
            query = state.get("contextualized_query", state.get("user_query", ""))

            if not query:
                return {"retrieved_docs": "", "retriever_query": "", "error": "No query provided"}

            # Retrieve documents
            documents = worker.retrieve_documents(query, state)

            # Format results
            if documents:
                doc_summaries = []
                for i, doc in enumerate(documents):
                    content = doc.page_content[:200]
                    source = doc.metadata.get("source", "Unknown") if doc.metadata else "Unknown"
                    doc_summaries.append(f"Doc {i+1}: {content}... (Source: {source})")

                result = f"Retrieved {len(documents)} documents:\n" + "\n".join(doc_summaries)
            else:
                result = "No relevant documents found for this query."

            return {"retrieved_docs": result, "retriever_query": query, "all_retrieved_docs": documents, "error": None}

        except Exception as e:
            return {"retrieved_docs": "", "retriever_query": state.get("contextualized_query", state.get("user_query", "")), "error": f"Retriever worker error: {str(e)}"}

    return retriever_worker
