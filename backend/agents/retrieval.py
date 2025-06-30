from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain.retrievers.ensemble import EnsembleRetriever
from langchain.runnables import RunnableLambda
from langchain_cohere import CohereRerank

from agents.graph_retrieval import expand_query_with_graph, graph_retrieval_agent
from agents.keyword_retrieval import keyword_retrieval_agent
from agents.state import AgentState
from agents.vector_retrieval import vector_retrieval_agent


def retrieval_agent(state: AgentState):
    """
    Retrieves documents from the various data stores (Qdrant, ElasticSearch, Neo4j)
    and applies metadata filters.
    """
    try:
        retrieval_selection = state.retrieval_selection
        methods = retrieval_selection["methods"]
        weights = retrieval_selection["weights"]

        retrievers = []

        # Perform query expansion if graph search is not the primary method
        expanded_queries = [state.transformed_query]
        if "graph" not in methods and state.entities:
            expanded_queries.extend(expand_query_with_graph(state.transformed_query, state.entities))
            expanded_queries = list(set(expanded_queries))  # Remove duplicates

        # Create a temporary state for each sub-agent to pass relevant fields
        temp_state = AgentState(
            query=state.query,
            chat_history=state.chat_history,
            transformed_query=state.transformed_query,
            metadata_filters=state.metadata_filters,
            priorities=state.priorities,
            entities=state.entities,
            structured_query=state.structured_query,
            statistical_query=state.statistical_query,
        )

        for part in methods:
            part = part.lower().strip()
            if part == "graph":
                retrievers.append(RunnableLambda(lambda x: graph_retrieval_agent(temp_state)))
            elif part == "dense":
                # Use expanded queries for dense retrieval
                retrievers.append(RunnableLambda(lambda x: vector_retrieval_agent(temp_state)))
            elif part == "sparse":
                # Use expanded queries for sparse retrieval
                retrievers.append(RunnableLambda(lambda x: keyword_retrieval_agent(temp_state)))

        if not retrievers:
            # Default to dense retrieval if no methods are specified
            retrievers.append(RunnableLambda(lambda x: vector_retrieval_agent(temp_state)))
            weights = [1.0]

        if len(weights) != len(retrievers):
            weights = [1.0 / len(retrievers)] * len(retrievers)

        # Create the EnsembleRetriever
        ensemble_retriever = EnsembleRetriever(retrievers=retrievers, weights=weights)

        # Combine results from all retrievers using expanded queries
        all_docs = []
        for query_term in expanded_queries:
            # The EnsembleRetriever expects a single query, so we'll invoke it once per expanded query
            # and then combine the results.
            # Note: The new agents expect AgentState, so we need to adjust how ensemble_retriever is invoked
            # For now, we'll pass the query_term as the 'question' in a dummy dict for the RunnableLambda
            # This might need further refinement depending on how EnsembleRetriever handles RunnableLambda inputs
            result = ensemble_retriever.invoke({"question": query_term})
            if isinstance(result, dict) and "documents" in result:
                all_docs.extend(result["documents"])
            elif isinstance(result, list):  # If the RunnableLambda directly returns a list of documents
                all_docs.extend(result)

        # Deduplicate documents based on page_content and metadata (source, title)
        unique_docs = {}
        for doc in all_docs:
            doc_id = (
                doc.page_content,
                doc.metadata.get("source"),
                doc.metadata.get("title"),
            )
            unique_docs[doc_id] = doc
        documents = list(unique_docs.values())

        # Apply re-ranking after combining all docs
        compressor = CohereRerank(model="rerank-english-v3.0")
        compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=RunnableLambda(lambda x: x))
        documents = compression_retriever.invoke(documents)

        # Add a specific tag to the documents for easier identification in streaming
        for doc in documents:
            doc.metadata["stream_tag"] = "final_retrieved_docs"

        return {"documents": documents}
    except Exception as e:
        return {"error": str(e)}
