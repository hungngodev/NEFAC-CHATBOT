from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    FACTUAL_STRATEGY_FORMAT_DOCUMENTS,
    FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY,
    FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class FactualStrategyState(QueryTransformerState):
    """State for the factual strategy subgraph."""

    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
def generate_factual_query_node(state: FactualStrategyState, config: RunnableConfig) -> RetrievalSubgraphState:
    """Generates a factual query and passes it to the retrieval subgraph."""
    question = state["transformed_query"]
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.factual_strategy_model)

    prompt = ChatPromptTemplate.from_template(configuration.factual_strategy_prompt)
    chain = prompt | llm | StrOutputParser()

    factual_query = chain.invoke({"question": question})
    # Pass the new query to the retrieval subgraph
    return {"retrieval_query": factual_query}


def format_documents_node(state: FactualStrategyState) -> QueryTransformerState:
    """Formats the retrieved documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"transformed_context": formatted_string}


workflow = StateGraph(FactualStrategyState)

workflow.add_node(FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY, generate_factual_query_node)
workflow.add_node(FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH, retrieval_subgraph)
workflow.add_node(FACTUAL_STRATEGY_FORMAT_DOCUMENTS, format_documents_node)

workflow.set_entry_point(FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY)
workflow.add_edge(FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY, FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH)
workflow.add_edge(FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH, FACTUAL_STRATEGY_FORMAT_DOCUMENTS)
workflow.add_edge(FACTUAL_STRATEGY_FORMAT_DOCUMENTS, END)

factual_strategy = workflow.compile()
