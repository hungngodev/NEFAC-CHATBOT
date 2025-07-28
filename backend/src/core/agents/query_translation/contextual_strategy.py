from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    CONTEXTUAL_STRATEGY_FORMAT_DOCUMENTS,
    CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY,
    CONTEXTUAL_STRATEGY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class ContextualStrategyState(QueryTransformerState):
    """State for the contextual strategy subgraph."""


# --- Nodes ---
def generate_contextual_query_node(state: ContextualStrategyState, config: RunnableConfig) -> dict:
    """Generates a contextual query and passes it to the retrieval subgraph."""
    question = state["transformed_query"]

    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.contextual_strategy_model)

    prompt = ChatPromptTemplate.from_template(configuration.contextual_strategy_prompt)
    chain = prompt | llm | StrOutputParser()

    contextual_query = chain.invoke({"question": question})
    return {"retrieval_query": contextual_query}


def format_documents_node(state: ContextualStrategyState) -> dict:
    """Formats the retrieved documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"transformed_context": formatted_string}


workflow = StateGraph(ContextualStrategyState)

workflow.add_node(
    CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY,
    generate_contextual_query_node,
    metadata={"description": "Generates contextual query using LLM to enhance retrieval relevance", "dependencies": ["transformed_query"], "outputs": ["retrieval_query"], "strategy": "contextual_enhancement", "expected_duration": "2-4s", "model_type": "contextual_strategy_model"},
)

workflow.add_node(
    CONTEXTUAL_STRATEGY_RETRIEVE_SUBGRAPH,
    retrieval_subgraph,
    metadata={"description": "Retrieval subgraph for contextual strategy", "dependencies": ["retrieval_query"], "outputs": ["documents"], "strategy": "multi_strategy_retrieval", "expected_duration": "3-8s", "retrieval_methods": ["vector", "hybrid", "knowledge_graph"]},
)

workflow.add_node(
    CONTEXTUAL_STRATEGY_FORMAT_DOCUMENTS,
    format_documents_node,
    metadata={"description": "Formats retrieved documents into single string for context", "dependencies": ["documents"], "outputs": ["transformed_context"], "strategy": "document_formatting", "expected_duration": "0.5-1s", "formatter": "format_docs"},
)

workflow.add_edge(START, CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY)
workflow.add_edge(CONTEXTUAL_STRATEGY_GENERATE_CONTEXTUAL_QUERY, CONTEXTUAL_STRATEGY_RETRIEVE_SUBGRAPH)
workflow.add_edge(CONTEXTUAL_STRATEGY_RETRIEVE_SUBGRAPH, CONTEXTUAL_STRATEGY_FORMAT_DOCUMENTS)
workflow.add_edge(CONTEXTUAL_STRATEGY_FORMAT_DOCUMENTS, END)

contextual_strategy = workflow.compile(
    debug=True,
    name="contextual_strategy_sequence",
)
