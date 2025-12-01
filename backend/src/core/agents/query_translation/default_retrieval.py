from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    DEFAULT_RETRIEVAL_FORMAT,
    DEFAULT_RETRIEVAL_RETRIEVE,
)
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState
from src.utils.debug import get_debug_mode


async def retrieve_node(state: QueryTransformerState, config: RunnableConfig) -> QueryTransformerState:
    """
    Direct retrieval using the original query without transformation.
    """
    query = state["transformed_query"]

    result = await retrieval_subgraph.ainvoke({"retrieval_query": query})

    documents = result.get("documents", [])

    return {"documents": documents}


def format_documents_node(state: QueryTransformerState) -> QueryTransformerState:
    """Formats the retrieved documents into a single string."""
    formatted_string = format_docs(state["documents"])
    return {"transformed_context": formatted_string}


workflow = StateGraph(QueryTransformerState)

workflow.add_node(DEFAULT_RETRIEVAL_RETRIEVE, retrieve_node, metadata={"description": "Direct retrieval using transformed query", "dependencies": ["transformed_query"], "outputs": ["documents"], "strategy": "direct_retrieval", "expected_duration": "2-5s", "retrieval_method": "vector_search"})

workflow.add_node(
    DEFAULT_RETRIEVAL_FORMAT, format_documents_node, metadata={"description": "Formats retrieved documents into single string", "dependencies": ["documents"], "outputs": ["transformed_context"], "strategy": "document_formatting", "expected_duration": "0.5-1s", "formatter": "format_docs"}
)

workflow.add_edge(START, DEFAULT_RETRIEVAL_RETRIEVE)
workflow.add_edge(DEFAULT_RETRIEVAL_RETRIEVE, DEFAULT_RETRIEVAL_FORMAT)
workflow.add_edge(DEFAULT_RETRIEVAL_FORMAT, END)

default_retrieval = workflow.compile(
    debug=get_debug_mode(),
    name="default_retrieval_sequence",
)
