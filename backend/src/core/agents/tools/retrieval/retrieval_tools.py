"""
Enhanced Retrieval Tools Architecture
Combines intelligent strategy selection, proper typing, advanced error handling, and query expansion.
Merged best practices from retrieval_tools.py, retrieval.py, and ensemble_retriever_tool.py
"""

import logging
import time
from typing import List, Optional

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever

from src.core.agents.tools.retrieval.graph_retrieval import expand_query_with_graph, graph_retrieval_agent
from src.core.agents.tools.retrieval.keyword_retrieval import get_bm25_retriever
from src.core.agents.tools.retrieval.vector_retrieval import get_qdrant_retriever
from src.exceptions.agent_exceptions import RetrievalError, handle_agent_exception
from src.schemas.core_types import AgentState, ReactAgentRetrievalOutput, RetrievalData, RetrievalMethod, RetrievalResult, RetrievalStrategy, RetrieverWorkerOutput, create_error_result, create_success_result

logger = logging.getLogger(__name__)

RETRIEVAL_METHOD_SELECTION_PROMPT = """
You are a retrieval-method selection agent for NEFAC’s First Amendment resources (https://nefac.org).

Your task is to analyze the user’s reformulated question and choose the most appropriate retrieval strategy or combination of strategies. NEFAC supports three retrieval methods:

• graph   – query NEFAC’s Neo4j knowledge graph of entities and relationships (e.g., laws, court cases, organizations); best for structured data or entity-linked queries  
• dense   – run a semantic vector search over NEFAC’s full-text corpus; best for broad, conceptual questions or those using synonyms and abstract ideas  
• sparse  – perform an Elasticsearch BM25 keyword search; best for exact terms, named references, or direct citations

Guidelines:
- Use **dense** for open-ended, conceptual, or exploratory queries
- Use **sparse** for keyword-heavy queries, legal citations, names, or precise terms
- Use **graph** when the query relates to structured data, named entities, or relationships (e.g., “Who funds NEFAC?”, “What law did X case involve?”)
- Combine methods for multi-faceted or ambiguous queries
- Weigh your selection based on query complexity, specificity, and the presence of legal or named entities

After your reasoning, return only a comma-separated list of selected strategies (e.g., `graph, sparse` or `dense`).
"""


class GraphRetriever(BaseRetriever):
    """
    Enhanced RetrieverLike wrapper for graph_retrieval_agent to be used with EnsembleRetriever.
    """

    def __init__(self, state: AgentState):
        self.state = state

    def invoke(self, input_query: str, **kwargs) -> List[Document]:
        """Invoke graph retrieval with proper state handling."""
        try:
            updated_state = self.state.model_copy(update={"transformed_query": input_query})
            return graph_retrieval_agent(updated_state)
        except Exception as e:
            logger.warning(f"Graph retrieval failed: {e}")
            return []

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        return self.invoke(query, **kwargs)


class RetrievalWorker:
    """
    Enhanced retrieval worker with intelligent strategy selection and comprehensive error handling.
    """

    def __init__(self, llm=None):
        self.llm = llm
        self.agent_name = "RetrievalWorker"
        self.available_methods = {"dense": "Semantic/vector search using embeddings", "sparse": "Keyword-based search using BM25", "graph": "Structured knowledge graph search"}

    def select_retrieval_strategy(self, input: str, context: Optional[AgentState] = None) -> RetrievalStrategy:
        """Intelligently select retrieval methods based on query characteristics."""

        if self.llm:
            return self._llm_strategy_selection(input, context)
        else:
            return self._rule_based_strategy_selection(input, context)

    def _llm_strategy_selection(self, input: str, context: Optional[AgentState] = None) -> RetrievalStrategy:
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

    def _rule_based_strategy_selection(self, input: str, context: Optional[AgentState] = None) -> RetrievalStrategy:
        """Enhanced rule-based fallback strategy selection."""

        query_lower = input.lower()
        methods = []
        weights = []
        reasoning_parts = []

        # Enhanced query patterns
        entity_patterns = ["who is", "what is", "relationship", "connected", "related to", "organization", "person", "case", "statute", "entity", "between", "association", "link", "connection"]

        exact_term_patterns = ["foia", "public records", "sunshine law", "exemption", "massachusetts", "rhode island", "connecticut", "section", "chapter", "subsection", "paragraph", "clause"]

        concept_patterns = ["similar", "like", "about", "regarding", "concerning", "concept", "principle", "approach", "method", "theory", "philosophy", "doctrine", "practice"]

        # Enhanced pattern detection
        has_entities = any(pattern in query_lower for pattern in entity_patterns)
        has_exact_terms = any(pattern in query_lower for pattern in exact_term_patterns) or '"' in input or input.isupper()  # All caps might indicate specific terms
        has_concepts = any(pattern in query_lower for pattern in concept_patterns)

        # Check for question words that might indicate conceptual queries
        question_words = ["how", "why", "when", "where", "explain", "describe"]
        has_conceptual_question = any(word in query_lower for word in question_words)

        if has_conceptual_question and not has_concepts:
            has_concepts = True

        # Default to dense for general queries
        if not (has_entities or has_exact_terms or has_concepts):
            has_concepts = True

        # Build strategy with intelligent weight distribution
        base_weight = 0.4

        if has_entities:
            methods.append("graph")
            weights.append(base_weight)
            reasoning_parts.append("graph search for entity relationships")

        if has_exact_terms:
            methods.append("sparse")
            # Give higher weight to sparse if query has quotes or specific legal terms
            weight = 0.5 if '"' in input else base_weight
            weights.append(weight)
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

        # Enable query expansion for multi-method strategies
        query_expansion = len(methods) > 1

        # Enable reranking for better results
        rerank = True

        return RetrievalStrategy(methods=methods, weights=weights, reasoning=reasoning, query_expansion=query_expansion, rerank=rerank)

    def _expand_queries(self, query: str, methods: List[str], entities: Optional[List[str]] = None, state: Optional[AgentState] = None) -> List[str]:
        """Expand queries using graph relationships if applicable."""
        expanded_queries = [query]

        # Only expand if we have entities and graph method is not already selected
        if "graph" not in methods and entities:
            try:
                from src.core.agents.tools.retrieval.graph_retrieval import Entities

                entities_obj = Entities(names=entities, types=None)
                graph_expanded = expand_query_with_graph(query, entities_obj)
                expanded_queries.extend(graph_expanded)
                expanded_queries = list(set(expanded_queries))  # Remove duplicates
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}")

        return expanded_queries

    def create_ensemble_retriever(self, strategy: RetrievalStrategy, state: AgentState) -> EnsembleRetriever:
        """Create ensemble retriever based on strategy with enhanced error handling."""

        retrievers = []
        successful_methods = []

        for method in strategy.methods:
            try:
                if method == "dense":
                    retrievers.append(get_qdrant_retriever())
                    successful_methods.append(method)
                elif method == "sparse":
                    retrievers.append(get_bm25_retriever())
                    successful_methods.append(method)
                elif method == "graph":
                    retrievers.append(GraphRetriever(state))
                    successful_methods.append(method)
            except Exception as e:
                logger.warning(f"Failed to initialize {method} retriever: {e}")
                continue

        # Fallback if no retrievers were successfully created
        if not retrievers:
            try:
                retrievers = [get_qdrant_retriever()]
                strategy.weights = [1.0]
                successful_methods = ["dense"]
                logger.info("Falling back to dense retriever only")
            except Exception as e:
                logger.error(f"Failed to create fallback retriever: {e}")
                raise RetrievalError(f"No retrievers could be initialized: {e}")

        # Adjust weights to match successful retrievers
        if len(strategy.weights) != len(retrievers):
            strategy.weights = [1.0 / len(retrievers)] * len(retrievers)
            logger.info(f"Adjusted weights for {len(retrievers)} successful retrievers")

        # Update strategy to reflect actually used methods
        strategy.methods = successful_methods

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

    def retrieve_documents(self, input_query: str, state: AgentState, max_docs: int = 10) -> RetrievalResult:
        """
        Main retrieval method with comprehensive error handling and performance tracking.
        Always returns RetrievalResult with structured metadata.
        """
        start_time = time.time()

        try:
            # Extract configuration from state
            entities = state.entities or []
            # retrieval_config = getattr(state, "retrieval_selection", {})  # Unused variable

            # 1. Select retrieval strategy
            strategy = self.select_retrieval_strategy(input_query, state)
            logger.info(f"Selected strategy: {strategy.reasoning}")

            # 2. Expand queries if needed
            expanded_queries = self._expand_queries(input_query, strategy.methods, entities, state)

            if len(expanded_queries) > 1:
                logger.info(f"Expanded query to {len(expanded_queries)} variants")

            # 3. Create ensemble retriever
            ensemble_retriever = self.create_ensemble_retriever(strategy, state)

            # 4. Retrieve documents from all queries
            all_documents = []
            for query in expanded_queries:
                if query and query.strip():
                    try:
                        docs = ensemble_retriever.invoke(query)
                        all_documents.extend(docs)
                    except Exception as e:
                        logger.error(f"Retrieval failed for query '{query}': {e}")

            # 5. Deduplicate
            unique_documents = self.deduplicate_documents(all_documents)

            # 6. Apply reranking if requested and we have documents
            final_documents = unique_documents
            reranking_applied = False
            if strategy.rerank and unique_documents:
                reranked_docs = self.apply_reranking(unique_documents, input_query)
                if reranked_docs:  # Only use reranked if successful
                    final_documents = reranked_docs
                    reranking_applied = True

            # 7. Limit results
            final_documents = final_documents[:max_docs]

            # 8. Add comprehensive metadata
            for i, doc in enumerate(final_documents):
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update({"retrieval_strategy": strategy.methods, "retrieval_rank": i + 1, "stream_tag": "retrieved_docs", "strategy_reasoning": strategy.reasoning})

            # 9. Calculate execution time
            execution_time = (time.time() - start_time) * 1000

            # Create structured result
            data = RetrievalData(
                documents=final_documents,
                retrieval_methods_used=[RetrievalMethod(m) for m in strategy.methods],
                total_documents_found=len(all_documents),
                documents_after_deduplication=len(unique_documents),
                deduplication_applied=len(all_documents) != len(unique_documents),
                reranking_applied=reranking_applied,
                query_expansion_applied=len(expanded_queries) > 1,
                retrieval_time_ms=execution_time,
            )

            return create_success_result(data=data, execution_time_ms=execution_time, methods_used=",".join(strategy.methods))

        except RetrievalError:
            raise
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = f"Retrieval error: {str(e)}"
            logger.error(error_msg)

            error = handle_agent_exception(e, self.agent_name, {"query": input_query, "retrieval_methods": getattr(state, "retrieval_selection", {})})
            return create_error_result(error=str(error), execution_time_ms=execution_time)


def create_retrieval_tool(llm=None):
    """Factory function to create a retrieval tool with string interface."""

    worker = RetrievalWorker(llm)

    def retrieval_tool(input_query: str, state: AgentState) -> str:
        """Retrieval tool with clean string interface."""

        try:
            result = worker.retrieve_documents(input_query, state)

            if result.is_success:
                docs = result.data.documents
                if not docs:
                    return "No relevant documents found for this query."

                # Format results with metadata
                doc_summaries = []
                for i, doc in enumerate(docs[:5]):  # Top 5 docs
                    content = doc.page_content[:200] if doc.page_content else "No content"
                    source = doc.metadata.get("source", "Unknown") if doc.metadata else "Unknown"
                    doc_summaries.append(f"Doc {i+1}: {content}... (Source: {source})")

                strategy_info = f"Strategy: {', '.join(result.data.retrieval_methods_used)} "
                strategy_info += f"({result.data.retrieval_time_ms:.1f}ms)"

                return f"Retrieved {len(docs)} documents using {strategy_info}:\n" + "\n".join(doc_summaries)
            else:
                return f"Retrieval failed: {result.error}"

        except Exception as e:
            return f"Retrieval error: {str(e)}"

    return retrieval_tool


# Types now imported above


def create_retriever_worker_function(llm=None):
    """Factory function to create a retriever worker function."""

    worker = RetrievalWorker(llm)

    def retriever_worker(state: AgentState) -> RetrieverWorkerOutput:
        """Retriever worker for direct queries with structured interface."""

        try:
            query = state.contextualized_query or state.user_query

            if not query:
                return {"retrieved_docs": "", "retriever_query": "", "error": "No query provided"}

            # Retrieve documents
            result = worker.retrieve_documents(query, state)

            if result.is_success:
                docs = result.data.documents

                # Format results
                if docs:
                    doc_summaries = []
                    for i, doc in enumerate(docs):
                        content = doc.page_content[:200] if doc.page_content else "No content"
                        source = doc.metadata.get("source", "Unknown") if doc.metadata else "Unknown"
                        doc_summaries.append(f"Doc {i+1}: {content}... (Source: {source})")

                    formatted_result = f"Retrieved {len(docs)} documents:\n" + "\n".join(doc_summaries)
                else:
                    formatted_result = "No relevant documents found for this query."

                return {
                    "retrieved_docs": formatted_result,
                    "retriever_query": query,
                    "all_retrieved_docs": docs,
                    "retrieval_metadata": {
                        "methods_used": [m.value for m in result.data.retrieval_methods_used],
                        "total_found": result.data.total_documents_found,
                        "deduplication_applied": result.data.deduplication_applied,
                        "reranking_applied": result.data.reranking_applied,
                        "execution_time_ms": result.data.retrieval_time_ms,
                    },
                    "error": None,
                }
            else:
                return {"retrieved_docs": "", "retriever_query": query, "all_retrieved_docs": [], "error": result.error}

        except Exception as e:
            return {"retrieved_docs": "", "retriever_query": getattr(state, "contextualized_query", "") or getattr(state, "user_query", ""), "all_retrieved_docs": [], "error": f"Retriever worker error: {str(e)}"}

    return retriever_worker


# ReactAgentRetrievalOutput now imported from types.py


# Universal Ensemble Retriever Tool - Integrated from ensemble_retriever_tool.py
class EnsembleRetrieverTool(BaseRetriever):
    """
    Universal ensemble retriever tool that can be used by:
    - Query translation strategies (RAG Fusion, HyDE, Step-back, etc.)
    - ReAct multi-step reasoning agent
    - Any other component needing retrieval

    Acts as both a LangChain BaseRetriever and a standalone tool.
    """

    def __init__(self, llm=None, default_methods: Optional[List[str]] = None, default_weights: Optional[List[float]] = None):
        """
        Initialize the ensemble retriever tool.

        Args:
            llm: Language model for intelligent strategy selection
            default_methods: Default retrieval methods to use ["dense", "sparse", "graph"]
            default_weights: Default weights for the methods [0.4, 0.3, 0.3]
        """
        super().__init__()
        self.worker = RetrievalWorker(llm)
        self.default_methods = default_methods or ["dense", "sparse", "graph"]
        self.default_weights = default_weights or [0.4, 0.3, 0.3]

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """
        LangChain BaseRetriever interface - for query translation strategies.
        """
        return self.retrieve(query, **kwargs)

    def invoke(self, query: str, **kwargs) -> List[Document]:
        """
        LangChain invoke interface - for query translation strategies.
        """
        return self.retrieve(query, **kwargs)

    def retrieve(self, query: str, methods: Optional[List[str]] = None, weights: Optional[List[float]] = None, entities: Optional[List[str]] = None, max_documents: int = 10, **kwargs) -> List[Document]:
        """
        Universal retrieval method that can be called by any component.

        Args:
            query: The search query
            methods: Retrieval methods to use (defaults to all three)
            weights: Weights for ensemble combination
            entities: Extracted entities for graph retrieval
            max_documents: Maximum number of documents to return
            **kwargs: Additional parameters

        Returns:
            List of retrieved documents
        """
        try:
            # Use provided methods/weights or defaults
            methods = methods or self.default_methods
            weights = weights or self.default_weights

            # Create a minimal state for the retrieval worker
            state = AgentState(
                query=query,
                contextualized_query=query,
                retrieval_selection={"methods": methods, "weights": weights},
                entities=entities or [],
                chat_history=[],  # Empty for tool usage
            )

            # Use the enhanced RetrievalWorker
            result = self.worker.retrieve_documents(query, state, max_documents)

            if result.is_success:
                documents = result.data.documents

                # Add tool metadata
                for doc in documents:
                    if not hasattr(doc, "metadata") or doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata.update({"retrieval_tool": "ensemble_retriever", "methods_used": methods, "ensemble_weights": weights, "execution_time_ms": result.data.retrieval_time_ms})

                return documents
            else:
                # Return empty list on error (graceful degradation)
                logger.warning(f"Retrieval failed: {result.error}")
                return []

        except Exception as e:
            # Log error but don't break the chain
            logger.error(f"EnsembleRetrieverTool error: {e}")
            return []

    def retrieve_for_react_agent(self, state: AgentState) -> ReactAgentRetrievalOutput:
        """
        Specialized method for ReAct multi-step reasoning agent.
        Returns the full result structure expected by ReAct agent.

        Args:
            state: AgentState with query and context

        Returns:
            Dict with documents and metadata
        """
        try:
            query = state.contextualized_query or state.user_query
            result = self.worker.retrieve_documents(query, state)

            if result.is_success:
                return {
                    "documents": result.data.documents,
                    "retrieval_metadata": {
                        "methods_used": [m.value for m in result.data.retrieval_methods_used],
                        "total_found": result.data.total_documents_found,
                        "deduplication_applied": result.data.deduplication_applied,
                        "reranking_applied": result.data.reranking_applied,
                        "execution_time_ms": result.data.retrieval_time_ms,
                        "query_expansion_applied": result.data.query_expansion_applied,
                    },
                }
            else:
                return {"documents": [], "error": result.error}

        except Exception as e:
            return {"documents": [], "error": f"Ensemble retrieval error: {str(e)}"}


# Main Retrieval Agent - Simplified and Enhanced
class RetrievalAgent:
    """
    Main retrieval agent with full typing support and advanced features.
    Main retrieval agent for the current system.
    """

    def __init__(self, llm=None):
        self.worker = RetrievalWorker(llm)

    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """
        Main interface for retrieving documents with full typing support.
        """
        query = state.contextualized_query or state.user_query
        return self.worker.retrieve_documents(query, state)


# Factory functions for ensemble retrievers
def get_ensemble_retriever(llm=None, methods: Optional[List[str]] = None, weights: Optional[List[float]] = None) -> EnsembleRetrieverTool:
    """
    Factory function to get an ensemble retriever with specific configuration.

    Args:
        llm: Language model for intelligent strategy selection
        methods: Retrieval methods to use
        weights: Weights for ensemble combination

    Returns:
        Configured EnsembleRetrieverTool instance
    """
    return EnsembleRetrieverTool(llm=llm, default_methods=methods, default_weights=weights)


def get_ensemble_retriever_for_query_translation(llm=None) -> EnsembleRetrieverTool:
    """
    Get ensemble retriever optimized for query translation strategies.
    Balanced weights for comprehensive coverage.
    """
    return EnsembleRetrieverTool(llm=llm, default_methods=["dense", "sparse", "graph"], default_weights=[0.4, 0.3, 0.3])  # Favor semantic but include all


def get_ensemble_retriever_for_react(llm=None) -> EnsembleRetrieverTool:
    """
    Get ensemble retriever optimized for ReAct multi-step reasoning.
    Emphasizes graph relationships for complex reasoning.
    """
    return EnsembleRetrieverTool(llm=llm, default_methods=["dense", "sparse", "graph"], default_weights=[0.3, 0.2, 0.5])  # Favor graph for reasoning


# Global instances
_retrieval_agent = RetrievalAgent()
ensemble_retriever_tool = EnsembleRetrieverTool()


def retrieval_agent(state: AgentState) -> List[Document]:
    """
    Main interface function for document retrieval.
    Returns documents directly for compatibility with existing code.
    """
    result = _retrieval_agent.retrieve_documents(state)

    if result.is_success:
        return result.data.documents
    else:
        logger.error(f"Retrieval failed: {result.error}")
        return []
