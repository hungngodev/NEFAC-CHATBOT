from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    HYDE_GENERATE_FINAL_RESPONSE,
    HYDE_GENERATE_HYPOTHETICAL_DOCUMENT,
    HYDE_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.query_translation.query_transformer import QueryTransformerState
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs

# Create a default configuration for backward compatibility
default_config = Configuration()
llm = init_chat_model(default_config.hyde_model)


# --- Subgraph State ---
class HydeState(QueryTransformerState):
    """State for the HyDE query transformation subgraph."""

    hypothetical_document: str = ""
    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
def generate_hypothetical_document_node(state: HydeState, config: RunnableConfig) -> RetrievalSubgraphState:
    """Generates a hypothetical document to be used as the retrieval query."""
    question = state["transformed_query"]
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.hyde_model)

    hyde_prompt = ChatPromptTemplate.from_template(configuration.hyde_generation_prompt)
    chain = hyde_prompt | llm | StrOutputParser()

    hypothetical_document = chain.invoke({"question": question})
    # Pass the hypothetical document to the retrieval subgraph via the 'retrieval_query' field
    return {"retrieval_query": hypothetical_document}


def generate_final_response_node(state: HydeState, config: RunnableConfig) -> QueryTransformerState:
    """Generates a final response using the documents retrieved based on the HyDE query."""
    question = state["transformed_query"]
    # The retrieval subgraph has already populated the 'documents' field
    documents = state["documents"]
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.hyde_final_model)

    context = format_docs(documents)

    final_prompt = ChatPromptTemplate.from_template(configuration.hyde_final_prompt)
    chain = final_prompt | llm | StrOutputParser()

    final_response = chain.invoke({"context": context, "question": question})
    return {"transformed_context": final_response}


workflow = StateGraph(HydeState)

workflow.add_node(HYDE_GENERATE_HYPOTHETICAL_DOCUMENT, generate_hypothetical_document_node)
# The retrieval subgraph is now a single, atomic node in this workflow
workflow.add_node(HYDE_RETRIEVE_SUBGRAPH, retrieval_subgraph)
workflow.add_node(HYDE_GENERATE_FINAL_RESPONSE, generate_final_response_node)

workflow.set_entry_point(HYDE_GENERATE_HYPOTHETICAL_DOCUMENT)
workflow.add_edge(HYDE_GENERATE_HYPOTHETICAL_DOCUMENT, HYDE_RETRIEVE_SUBGRAPH)
workflow.add_edge(HYDE_RETRIEVE_SUBGRAPH, HYDE_GENERATE_FINAL_RESPONSE)
workflow.add_edge(HYDE_GENERATE_FINAL_RESPONSE, END)

hyde = workflow.compile()
