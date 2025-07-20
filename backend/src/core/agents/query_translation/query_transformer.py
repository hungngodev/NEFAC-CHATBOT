from functools import partial
from typing import ClassVar, Literal

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from backend.src.schemas.state import AgentState
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
from src.core.agents.query_translation.factual_strategy import factual_strategy
from src.core.agents.query_translation.hyde import hyde
from src.core.agents.query_translation.multi_query import multi_query
from src.core.agents.query_translation.step_back import step_back


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    method: Literal[
        "multiquery",
        "decompose",
        "stepback",
        "hyde",
        "ragfusion",
        "factual",
        "contextual",
    ] = Field(description="The selected query construction method.")


def route_to_transformer(state: AgentState, config: Configuration) -> str:
    """Routes to the appropriate query transformation subgraph based on the retrieval method."""
    llm = init_chat_model(config.query_transformer_model)
    method_chain = ChatPromptTemplate.from_template(config.query_transformer_prompt) | llm.with_structured_output(MethodSelection)
    question = state["contextualized_query"]
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
        return "multi_query"


workflow = StateGraph(AgentState)

workflow.add_node(QUERY_TRANSFORMER_MULTI_QUERY, multi_query)
workflow.add_node(QUERY_TRANSFORMER_DECOMPOSITION, decomposition)
workflow.add_node(QUERY_TRANSFORMER_STEP_BACK, step_back)
workflow.add_node(QUERY_TRANSFORMER_HYDE, hyde)
workflow.add_node(QUERY_TRANSFORMER_FACTUAL_STRATEGY, factual_strategy)
workflow.add_node(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, contextual_strategy)

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
    },
)

workflow.add_edge(QUERY_TRANSFORMER_MULTI_QUERY, END)
workflow.add_edge(QUERY_TRANSFORMER_DECOMPOSITION, END)
workflow.add_edge(QUERY_TRANSFORMER_STEP_BACK, END)
workflow.add_edge(QUERY_TRANSFORMER_HYDE, END)
workflow.add_edge(QUERY_TRANSFORMER_FACTUAL_STRATEGY, END)
workflow.add_edge(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, END)

query_transformer = workflow.compile()
