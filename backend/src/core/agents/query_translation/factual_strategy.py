from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    FACTUAL_STRATEGY_FORMAT_DOCUMENTS,
    FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY,
    FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState
from src.utils.debug import get_debug_mode
from src.utils.model_factory import init_model


# --- Subgraph State ---
class FactualStrategyState(QueryTransformerState):
    """State for the factual strategy subgraph."""

    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
async def generate_factual_query_node(state: FactualStrategyState, config: RunnableConfig) -> dict:
    """Generates a factual query and passes it to the retrieval subgraph."""
    question = state["transformed_query"]

    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.factual_strategy_model, disable_streaming=configuration.disable_streaming)

    prompt = ChatPromptTemplate.from_template(configuration.factual_strategy_prompt)
    chain = prompt | llm | StrOutputParser()

    factual_query = await chain.ainvoke({"question": question})
    return {"retrieval_query": factual_query}


def format_documents_node(state: FactualStrategyState) -> dict:
    """Formats the retrieved documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"transformed_context": formatted_string}


workflow = StateGraph(FactualStrategyState)

workflow.add_node(
    FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY,
    generate_factual_query_node,
    metadata={"description": "Generates factual query focused on precise information retrieval", "dependencies": ["transformed_query"], "outputs": ["retrieval_query"], "strategy": "factual_enhancement", "expected_duration": "2-4s", "model_type": "factual_strategy_model"},
)

workflow.add_node(
    FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH,
    retrieval_subgraph,
    metadata={"description": "Retrieval subgraph for factual strategy", "dependencies": ["retrieval_query"], "outputs": ["documents"], "strategy": "multi_strategy_retrieval", "expected_duration": "3-8s", "retrieval_methods": ["vector", "hybrid", "knowledge_graph"]},
)

workflow.add_node(
    FACTUAL_STRATEGY_FORMAT_DOCUMENTS,
    format_documents_node,
    metadata={"description": "Formats retrieved documents into single string for factual context", "dependencies": ["documents"], "outputs": ["transformed_context"], "strategy": "document_formatting", "expected_duration": "0.5-1s", "formatter": "format_docs"},
)

workflow.add_edge(START, FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY)
workflow.add_edge(FACTUAL_STRATEGY_GENERATE_FACTUAL_QUERY, FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH)
workflow.add_edge(FACTUAL_STRATEGY_RETRIEVE_SUBGRAPH, FACTUAL_STRATEGY_FORMAT_DOCUMENTS)
workflow.add_edge(FACTUAL_STRATEGY_FORMAT_DOCUMENTS, END)


factual_strategy = workflow.compile(
    debug=get_debug_mode(),
    name="factual_strategy_sequence",
)
