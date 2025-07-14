import logging
from typing import List, Union

from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from src.config.prompts import MULTI_QUERY_PERSPECTIVES_PROMPT
from src.core.agents.retrieval.subgraph import create_retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

logger = logging.getLogger(__name__)


# --- Subgraph State ---
class MultiQueryState(AgentState):
    """State for the multi-query subgraph."""
    generated_queries: List[str] = []
    # This field will hold lists of documents for each query
    retrieved_documents_lists: List[List[Document]] = []
    # This field will hold the final, deduplicated list of documents
    documents: List[Document] = []


# --- Nodes ---
def generate_queries_node(state: MultiQueryState, llm) -> dict:
    """Generates multiple queries from the user's question."""
    logger.info("Generating multiple queries for diversification.")
    question = state["contextualized_query"]
    prompt = ChatPromptTemplate.from_template(MULTI_QUERY_PERSPECTIVES_PROMPT)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.split("
"))

    generated_queries = chain.invoke({"question": question})
    # Filter out any empty strings that might result from splitting
    generated_queries = [q.strip() for q in generated_queries if q.strip()]

    logger.info(f"Generated {len(generated_queries)} queries.")
    return {"generated_queries": generated_queries}


def retrieval_node(state: MultiQueryState, retrieval_subgraph) -> dict:
    """Retrieves documents for each generated query using the retrieval subgraph."""
    logger.info("Retrieving documents for generated queries.")
    queries = state["generated_queries"]
    all_docs_lists = []

    for query in queries:
        logger.debug(f"Invoking retrieval subgraph for query: '{query}'")
        # The retrieval subgraph is invoked with a state containing the query
        result_state = retrieval_subgraph.invoke({"transformed_query": query})
        documents = result_state.get("documents", [])
        logger.debug(f"Retrieved {len(documents)} documents for query: '{query}'")
        all_docs_lists.append(documents)

    return {"retrieved_documents_lists": all_docs_lists}


def deduplicate_documents_node(state: MultiQueryState) -> dict:
    """Deduplicates documents from the multiple retrieval runs."""
    logger.info("Deduplicating retrieved documents.")
    retrieved_documents_lists = state["retrieved_documents_lists"]

    flattened_docs_str = []
    for doc_list in retrieved_documents_lists:
        for doc in doc_list:
            if isinstance(doc, Document):
                flattened_docs_str.append(dumps(doc))

    unique_docs_str = list(set(flattened_docs_str))

    unique_documents = []
    for doc_str in unique_docs_str:
        try:
            doc = loads(doc_str)
            if isinstance(doc, Document):
                unique_documents.append(doc)
        except Exception as e:
            logger.warning(f"Failed to load document from string: {e}")
            continue

    logger.info(f"Reduced from {len(flattened_docs_str)} to {len(unique_documents)} unique documents.")
    return {"documents": unique_documents}


def format_documents_node(state: MultiQueryState) -> dict:
    """Formats the final list of documents into a single string."""
    logger.info("Formatting final document list.")
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"transformed_query": formatted_string}


# --- Graph Definition ---
def create_multi_query_subgraph(llm):
    """
    Creates a subgraph that generates multiple queries, retrieves documents for each,
    deduplicates the results, and formats them.
    """
    retrieval_subgraph = create_retrieval_subgraph(llm)

    workflow = StateGraph(MultiQueryState)

    workflow.add_node("generate_queries", lambda state: generate_queries_node(state, llm))
    workflow.add_node("retrieve_documents", lambda state: retrieval_node(state, retrieval_subgraph))
    workflow.add_node("deduplicate_documents", deduplicate_documents_node)
    workflow.add_node("format_documents", format_documents_node)

    workflow.set_entry_point("generate_queries")
    workflow.add_edge("generate_queries", "retrieve_documents")
    workflow.add_edge("retrieve_documents", "deduplicate_documents")
    workflow.add_edge("deduplicate_documents", "format_documents")
    workflow.add_edge("format_documents", END)

    return workflow.compile()
