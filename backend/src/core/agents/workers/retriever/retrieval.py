import time
from typing import Dict, List, Union

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from src.core.agents.tools.retrieval.graph_retrieval import expand_query_with_graph, graph_retrieval_agent
from src.core.agents.tools.retrieval.keyword_retrieval import get_bm25_retriever
from src.core.agents.tools.retrieval.vector_retrieval import get_qdrant_retriever
from src.exceptions.agent_exceptions import RetrievalError, handle_agent_exception
from src.schemas.agent_types import RetrievalData, RetrievalMethod, RetrievalResult, create_error_result, create_success_result
from src.schemas.state import AgentState
from src.utils.validation import validate_retrieval_input


class GraphRetriever(BaseRetriever):
    """
    Minimal RetrieverLike wrapper for graph_retrieval_agent to be used with EnsembleRetriever.
    """

    def __init__(self, state: AgentState):
        self.state = state

    def invoke(self, input_query: str, **kwargs) -> List[Document]:
        # Set the transformed_query for the graph agent
        updated_state = self.state.model_copy(update={"transformed_query": input_query})
        return graph_retrieval_agent(updated_state)

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        return self.invoke(query, **kwargs)


class RetrievalAgent:
    """
    Retrieval agent with proper typing and error handling.
    """

    def __init__(self):
        self.agent_name = "Retriever"

    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """
        Retrieve documents using ensemble of retrieval methods.

        Args:
            state: Current agent state with query and retrieval configuration

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        start_time = time.time()

        try:
            # Extract and validate retrieval configuration
            retrieval_config = self._extract_retrieval_config(state)

            # Validate input
            validation = validate_retrieval_input(query=retrieval_config["query"], retrieval_methods=retrieval_config["methods"], weights=retrieval_config["weights"], max_documents=retrieval_config.get("max_documents", 10))

            # Expand queries if needed
            expanded_queries = self._expand_queries(query=validation.query, methods=validation.retrieval_methods, entities=state.entities or [])

            # Retrieve documents using ensemble approach
            all_documents = self._retrieve_with_ensemble(queries=expanded_queries, methods=validation.retrieval_methods, weights=validation.weights or [1.0 / len(validation.retrieval_methods)] * len(validation.retrieval_methods), state=state)

            # Deduplicate documents
            unique_documents = self._deduplicate_documents(all_documents)

            # Apply re-ranking if documents exist
            final_documents = self._apply_reranking(documents=unique_documents, query=validation.query)

            # Limit results
            final_documents = final_documents[: validation.max_documents]

            # Add metadata tags
            self._add_metadata_tags(final_documents)

            # Create result
            execution_time = (time.time() - start_time) * 1000

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

            return create_success_result(data=data, execution_time_ms=execution_time, methods_used=",".join([m.value for m in validation.retrieval_methods]))

        except RetrievalError:
            raise
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error = handle_agent_exception(e, self.agent_name, {"query": getattr(state, "user_query", "unknown"), "retrieval_methods": getattr(state, "retrieval_selection", {})})

            return create_error_result(error=str(error), execution_time_ms=execution_time)

    def _extract_retrieval_config(self, state: AgentState) -> Dict[str, Union[str, List[str], List[float]]]:
        """Extract retrieval configuration from state."""
        query = state.contextualized_query or state.user_query
        retrieval_selection = state.retrieval_selection or {"methods": ["dense"], "weights": [1.0]}
        methods = retrieval_selection.get("methods", ["dense"])
        weights = retrieval_selection.get("weights", [1.0])

        return {"query": query, "methods": methods, "weights": weights}

    def _expand_queries(self, query: str, methods: List[RetrievalMethod], entities: List[str]) -> List[str]:
        """Expand queries using graph relationships if applicable."""
        expanded_queries = [query]

        if RetrievalMethod.GRAPH not in methods and entities:
            try:
                from src.core.agents.tools.retrieval.graph_retrieval import Entities

                entities_obj = Entities(names=entities, types=None)
                graph_expanded = expand_query_with_graph(query, entities_obj)
                expanded_queries.extend(graph_expanded)
                expanded_queries = list(set(expanded_queries))
            except Exception as e:
                import logging

                logging.warning(f"Query expansion failed: {e}")

        return expanded_queries

    def _retrieve_with_ensemble(self, queries: List[str], methods: List[RetrievalMethod], weights: List[float], state: AgentState) -> List[Document]:
        """Retrieve documents using ensemble of methods."""
        retrievers = []

        for method in methods:
            try:
                if method == RetrievalMethod.DENSE:
                    retrievers.append(get_qdrant_retriever())
                elif method == RetrievalMethod.SPARSE:
                    retrievers.append(get_bm25_retriever())
                elif method == RetrievalMethod.GRAPH:
                    retrievers.append(GraphRetriever(state))
            except Exception as e:
                import logging

                logging.error(f"Failed to initialize {method.value} retriever: {e}")

        if not retrievers:
            retrievers = [get_qdrant_retriever()]
            weights = [1.0]

        if len(weights) != len(retrievers):
            weights = [1.0 / len(retrievers)] * len(retrievers)

        ensemble_retriever = EnsembleRetriever(retrievers=retrievers, weights=weights)

        all_documents = []
        for query in queries:
            if query and query.strip():
                try:
                    documents = ensemble_retriever.invoke(query)
                    all_documents.extend(documents)
                except Exception as e:
                    import logging

                    logging.error(f"Retrieval failed for query '{query}': {e}")

        return all_documents

    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """Deduplicate documents based on content and metadata."""
        unique_docs = {}

        for doc in documents:
            content = doc.page_content
            metadata = doc.metadata if hasattr(doc, "metadata") and doc.metadata else {}
            source = metadata.get("source", "unknown")
            title = metadata.get("title", "unknown")

            doc_key = (content, source, title)
            if doc_key not in unique_docs:
                unique_docs[doc_key] = doc

        return list(unique_docs.values())

    def _apply_reranking(self, documents: List[Document], query: str) -> List[Document]:
        """Apply re-ranking to improve document relevance."""
        if not documents:
            return documents

        try:
            compressor = CohereRerank(model="rerank-english-v3.0")

            class IdentityRetriever:
                def __init__(self, docs):
                    self.docs = docs

                def invoke(self, input_query: str) -> List[Document]:
                    return self.docs

                def get_relevant_documents(self, query: str) -> List[Document]:
                    return self.invoke(query)

            identity_retriever = IdentityRetriever(documents)
            compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=identity_retriever)

            reranked_docs = compression_retriever.invoke(query)
            return reranked_docs

        except Exception as e:
            import logging

            logging.warning(f"Reranking failed: {e}")
            return documents

    def _add_metadata_tags(self, documents: List[Document]) -> None:
        """Add metadata tags to documents for identification."""
        for doc in documents:
            if not hasattr(doc, "metadata") or doc.metadata is None:
                doc.metadata = {}
            doc.metadata["stream_tag"] = "final_retrieved_docs"


# Create global instance
_retrieval_agent = RetrievalAgent()


def retrieval_agent(state: AgentState) -> List[Document]:
    """
    Main interface function - uses the improved agent implementation.
    Returns documents directly for backward compatibility.
    """
    result = _retrieval_agent.retrieve_documents(state)

    if result.is_success:
        return result.data.documents
    else:
        # Return empty list on error for backward compatibility
        return []
