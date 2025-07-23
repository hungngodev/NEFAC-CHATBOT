from typing import List

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig, Send

from src.config.node_names import (
    MULTI_QUERY_DEDUPLICATE_DOCUMENTS,
    MULTI_QUERY_FORMAT_DOCUMENTS,
    MULTI_QUERY_GENERATE_QUERIES,
    MULTI_QUERY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class MultiQueryState(QueryTransformerState):
    """State for the multi-query subgraph."""

    generated_queries: List[str] = []


# --- Nodes ---
def generate_queries_node(state: MultiQueryState, config: RunnableConfig) -> MultiQueryState:
    """
    Generates multiple queries and returns a list of Send objects
    to trigger parallel retrieval for each query.
    """
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.multi_query_model)

    question = state["transformed_query"]
    prompt = ChatPromptTemplate.from_template(configuration.multi_query_perspectives_prompt)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))

    generated_queries = chain.invoke({"question": question})
    generated_queries = [q.strip() for q in generated_queries if q.strip()]

    # For each query, Send it to the retrieval subgraph
    # Each invocation will have its own `retrieval_query`
    return {"generated_queries": generated_queries}


def deduplicate_documents_node(state: RetrievalSubgraphState, config: RunnableConfig) -> MultiQueryState:
    """
    Deduplicates documents from the multiple parallel retrieval runs.
    The results from the Send operations are automatically collected in the state.
    """
    # The `retrieved_documents_lists` will contain the output of each retrieval subgraph invocation
    retrieved_documents_lists = state["accumulated_documents"]

    flattened_docs_str = []

    for doc in retrieved_documents_lists:
        if isinstance(doc, Document):
            flattened_docs_str.append(dumps(doc))

    unique_docs_str = list(set(flattened_docs_str))

    unique_documents = []
    for doc_str in unique_docs_str:
        doc = loads(doc_str)
        if isinstance(doc, Document):
            unique_documents.append(doc)
    return {"accumulated_documents": unique_documents}


def format_documents_node(state: MultiQueryState) -> QueryTransformerState:
    """Formats the final list of documents into a single string."""
    formatted_string = format_docs(state["accumulated_documents"])
    # The final output of any query translation subgraph is the transformed query/result
    return {"transformed_context": formatted_string}


workflow = StateGraph(MultiQueryState)

workflow.add_node(MULTI_QUERY_GENERATE_QUERIES, generate_queries_node)
workflow.add_node(MULTI_QUERY_RETRIEVE_SUBGRAPH, retrieval_subgraph)
workflow.add_node(MULTI_QUERY_DEDUPLICATE_DOCUMENTS, deduplicate_documents_node)
workflow.add_node(MULTI_QUERY_FORMAT_DOCUMENTS, format_documents_node)
workflow.set_entry_point(MULTI_QUERY_GENERATE_QUERIES)


def route_from_generate_queries(state: MultiQueryState) -> List[Send]:
    """Route to multiple retrieval subgraph invocations based on generated queries."""
    queries = state["generated_queries"]
    sends = [Send(MULTI_QUERY_RETRIEVE_SUBGRAPH, {"retrieval_query": q}) for q in queries]
    return sends


workflow.add_conditional_edges(
    MULTI_QUERY_GENERATE_QUERIES,
    route_from_generate_queries,
)

# After all parallel retrieval runs are complete, they are joined at the next node
workflow.add_edge(MULTI_QUERY_RETRIEVE_SUBGRAPH, MULTI_QUERY_DEDUPLICATE_DOCUMENTS)
workflow.add_edge(MULTI_QUERY_DEDUPLICATE_DOCUMENTS, MULTI_QUERY_FORMAT_DOCUMENTS)
workflow.add_edge(MULTI_QUERY_FORMAT_DOCUMENTS, END)
multi_query = workflow.compile()
