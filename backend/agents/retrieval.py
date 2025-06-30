from langchain.runnables import RunnableLambda
from langchain_community.compression import ContextualCompressionRetriever
from langchain_community.compression.cohere import CohereRerank

from vector.bm25 import get_bm25_retriever
from vector.graph_search import expand_query_with_graph, graph_rag_retrieve
from vector.qdrant import get_qdrant_retriever

from .state import AgentState


def retrieval_agent(state: AgentState):
    """
    Retrieves documents from the vector stores.
    """
    try:
        retrieval_selection = state.retrieval_selection
        methods = retrieval_selection["methods"]
        weights = retrieval_selection["weights"]

        retrievers = []

        # Perform query expansion if graph search is not the primary method
        expanded_queries = [state.transformed_query]
        if "graph" not in methods and state.entities:
            expanded_queries.extend(
                expand_query_with_graph(state.transformed_query, state.entities)
            )
            expanded_queries = list(set(expanded_queries))  # Remove duplicates

        for part in methods:
            part = part.lower().strip()
            if part == "graph":
                retrievers.append(
                    RunnableLambda(
                        lambda inputs: (
                            {"documents": graph_rag_retrieve(inputs["question"])}
                            if isinstance(inputs, dict) and "question" in inputs
                            else {"documents": graph_rag_retrieve(str(inputs))}
                        )
                    )
                )
            elif part == "dense":
                # Use expanded queries for dense retrieval
                retrievers.append(get_qdrant_retriever())
            elif part == "sparse":
                # Use expanded queries for sparse retrieval
                retrievers.append(get_bm25_retriever())

        if not retrievers:
            retrievers.append(get_qdrant_retriever())
            weights = [1.0]

        if len(weights) != len(retrievers):
            weights = [1.0 / len(retrievers)] * len(retrievers)

        # Combine results from all retrievers using expanded queries
        all_docs = []
        for query_term in expanded_queries:
            for r in retrievers:
                # For graph retriever, pass the original transformed_query
                if "graph_rag_retrieve" in str(r):
                    all_docs.extend(r.invoke({"question": state.transformed_query}))
                else:
                    all_docs.extend(r.invoke(query_term))

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
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=RunnableLambda(lambda x: x)
        )
        documents = compression_retriever.invoke(all_docs)

        return {"documents": documents}
    except Exception as e:
        return {"error": str(e)}
