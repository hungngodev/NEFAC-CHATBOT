from functools import partial
from typing import ClassVar, List, Literal

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.config.node_names import (
    QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
    QUERY_TRANSFORMER_DECOMPOSITION,
    QUERY_TRANSFORMER_FACTUAL_STRATEGY,
    QUERY_TRANSFORMER_HYDE,
    QUERY_TRANSFORMER_MULTI_QUERY,
    QUERY_TRANSFORMER_STEP_BACK,
)
from src.config.settings import Configuration
from src.core.agents.query_translation.contextual_strategy import contextual_strategy
from src.core.agents.query_translation.decomposition import decomposition
from src.core.agents.query_translation.default_retrieval import default_retrieval
from src.core.agents.query_translation.factual_strategy import factual_strategy
from src.core.agents.query_translation.hyde import hyde
from src.core.agents.query_translation.multi_query import multi_query
from src.core.agents.query_translation.step_back import step_back
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState


class QueryTransformerState(RetrievalSubgraphState):
    """Standalone state for the query transformer workflow."""

    transformed_query: str  # The input query to transform
    method_used: Literal["multiquery", "decompose", "stepback", "hyde", "factual", "contextual", "default"]  # Which transformation method was applied
    transformed_context: str  # Formatted final context
    generated_queries: List[str]  # For multi-query strategy
    sub_questions: List[str]  # For decomposition strategy
    step_back_question: str  # For step-back strategy
    hypothetical_document: str  # For HyDE strategy


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    method: Literal["multiquery", "decompose", "stepback", "hyde", "ragfusion", "factual", "contextual", "default"] = Field(description="The selected query construction method.")


def route_to_transformer(state: QueryTransformerState, config: Configuration) -> str:
    """Routes to the appropriate query transformation subgraph based on the retrieval method."""
    llm = init_chat_model(config.query_transformer_model)
    method_chain = ChatPromptTemplate.from_template(config.query_transformer_prompt) | llm.with_structured_output(MethodSelection)
    question = state["transformed_query"]
    response = method_chain.invoke({"question": question})
    method = response.method.lower().strip()

    if "multiquery" in method:
        return "multi_query"
    elif "decompose" in method:
        return "decomposition"
    elif "stepback" in method:
        return "step_back"
    elif "hyde" in method:
        return "hyde"
    elif "factual" in method:
        return "factual_strategy"
    elif "contextual" in method:
        return "contextual_strategy"
    else:
        return "default_retrieval"


workflow = StateGraph(QueryTransformerState)

workflow.add_node(QUERY_TRANSFORMER_MULTI_QUERY, multi_query)
workflow.add_node(QUERY_TRANSFORMER_DECOMPOSITION, decomposition)
workflow.add_node(QUERY_TRANSFORMER_STEP_BACK, step_back)
workflow.add_node(QUERY_TRANSFORMER_HYDE, hyde)
workflow.add_node(QUERY_TRANSFORMER_FACTUAL_STRATEGY, factual_strategy)
workflow.add_node(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, contextual_strategy)
workflow.add_node("default_retrieval", default_retrieval)

# Create a partial function to pass the config to the router
router = partial(route_to_transformer, config=Configuration())

workflow.set_conditional_entry_point(
    router,
    {
        "multi_query": QUERY_TRANSFORMER_MULTI_QUERY,
        "decomposition": QUERY_TRANSFORMER_DECOMPOSITION,
        "step_back": QUERY_TRANSFORMER_STEP_BACK,
        "hyde": QUERY_TRANSFORMER_HYDE,
        "factual_strategy": QUERY_TRANSFORMER_FACTUAL_STRATEGY,
        "contextual_strategy": QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
        "default_retrieval": "default_retrieval",
    },
)

workflow.add_edge(QUERY_TRANSFORMER_MULTI_QUERY, END)
workflow.add_edge(QUERY_TRANSFORMER_DECOMPOSITION, END)
workflow.add_edge(QUERY_TRANSFORMER_STEP_BACK, END)
workflow.add_edge(QUERY_TRANSFORMER_HYDE, END)
workflow.add_edge(QUERY_TRANSFORMER_FACTUAL_STRATEGY, END)
workflow.add_edge(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, END)
workflow.add_edge("default_retrieval", END)

query_transformer = workflow.compile()


async def query_internal_documents(query: str, config=None) -> QueryTransformerState:
    """
    Query internal documents using intelligent transformation strategies.

    Args:
        query (str): The query to transform and search
        config: Optional configuration for the workflow

    Returns:
        QueryTransformerState: Result with documents, final_context, method_used, etc.
    """
    initial_state = {
        "transformed_query": query,
        "method_used": "default",  # Will be updated by router
        "transformed_context": "",
        "generated_queries": [],
        "sub_questions": [],
        "step_back_question": "",
        "hypothetical_document": "",
        "retrieval_query": "",
        "retrieval_plan": {},
        "graph_documents": [],
        "document_search_documents": [],
        "documents": [],
        "accumulated_documents": [],
    }

    return await query_transformer.ainvoke(initial_state, config)
