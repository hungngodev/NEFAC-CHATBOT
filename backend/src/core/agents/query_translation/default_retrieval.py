from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    DEFAULT_RETRIEVAL_FORMAT,
    DEFAULT_RETRIEVAL_RETRIEVE,
)
from src.core.agents.query_translation.query_transformer import QueryTransformerState
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs


def retrieve_node(state: QueryTransformerState, config: RunnableConfig) -> QueryTransformerState:
    """
    Direct retrieval using the original query without transformation.
    """
    query = state["transformed_query"]

    # Invoke the retrieval subgraph directly
    result = retrieval_subgraph.invoke({"retrieval_query": query}, config)

    # Extract documents from the result
    documents = result.get("documents", [])

    return {"documents": documents}


def format_documents_node(state: QueryTransformerState) -> QueryTransformerState:
    """Formats the retrieved documents into a single string."""
    formatted_string = format_docs(state["documents"])
    return {"transformed_context": formatted_string}


# Build the default retrieval workflow
workflow = StateGraph(QueryTransformerState)

workflow.add_node(DEFAULT_RETRIEVAL_RETRIEVE, retrieve_node)
workflow.add_node(DEFAULT_RETRIEVAL_FORMAT, format_documents_node)

workflow.set_entry_point(DEFAULT_RETRIEVAL_RETRIEVE)
workflow.add_edge(DEFAULT_RETRIEVAL_RETRIEVE, DEFAULT_RETRIEVAL_FORMAT)
workflow.add_edge(DEFAULT_RETRIEVAL_FORMAT, END)

default_retrieval = workflow.compile()
