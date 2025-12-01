import os as _os
from typing import ClassVar, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.config.node_names import (
    QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
    QUERY_TRANSFORMER_DECOMPOSITION,
    QUERY_TRANSFORMER_DEFAULT_RETRIEVAL,
    QUERY_TRANSFORMER_FACTUAL_STRATEGY,
    QUERY_TRANSFORMER_HYDE,
    QUERY_TRANSFORMER_MULTI_QUERY,
    QUERY_TRANSFORMER_PREPARE_OUTPUT,
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
from src.schemas.state import QueryTransformerOutputState, QueryTransformerState
from src.utils.model_factory import init_model


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    method: Literal["multiquery", "decompose", "stepback", "hyde", "ragfusion", "factual", "contextual", "default"] = Field(description="The selected query construction method.")


async def route_to_transformer(state: QueryTransformerState, config: RunnableConfig) -> str:
    """Routes to the appropriate query transformation subgraph based on the retrieval method.

    Avoids any potential streaming by using a plain text parser instead of structured output.
    """
    configurable = Configuration.from_runnable_config(config)
    llm = init_model(configurable.query_transformer_model, disable_streaming=configurable.disable_streaming)
    method_chain = ChatPromptTemplate.from_template(configurable.query_transformer_prompt) | llm.with_structured_output(MethodSelection)
    question = state["transformed_query"]
    response = await method_chain.ainvoke({"question": question})
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


def prepare_output(state: QueryTransformerState) -> QueryTransformerOutputState:
    """Prepare output state for Send() API aggregation."""
    result = {
        "transformed_context": state.get("transformed_context", ""),
        "method_used": state.get("method_used", "default"),
        "_source_tool_call": state.get("_source_tool_call", {}),
        "transformed_query": state.get("transformed_query", ""),
    }

    return {"_completed_query_results": [result]}


workflow = StateGraph(QueryTransformerState, output=QueryTransformerOutputState, context_schema=Configuration)

workflow.add_node(QUERY_TRANSFORMER_MULTI_QUERY, multi_query, metadata={"description": "Multi-query generation strategy for comprehensive retrieval", "type": "strategy_subgraph", "strategy": "multi_query", "parallel_capable": True})

workflow.add_node(QUERY_TRANSFORMER_DECOMPOSITION, decomposition, metadata={"description": "Query decomposition strategy for complex questions", "type": "strategy_subgraph", "strategy": "decomposition", "iterative": True})

workflow.add_node(QUERY_TRANSFORMER_STEP_BACK, step_back, metadata={"description": "Step-back prompting strategy for better context", "type": "strategy_subgraph", "strategy": "step_back", "parallel_capable": True})

workflow.add_node(QUERY_TRANSFORMER_HYDE, hyde, metadata={"description": "Hypothetical Document Embeddings strategy", "type": "strategy_subgraph", "strategy": "hyde", "llm_powered": True})

workflow.add_node(QUERY_TRANSFORMER_FACTUAL_STRATEGY, factual_strategy, metadata={"description": "Factual information retrieval strategy", "type": "strategy_subgraph", "strategy": "factual"})

workflow.add_node(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, contextual_strategy, metadata={"description": "Contextual information retrieval strategy", "type": "strategy_subgraph", "strategy": "contextual"})

workflow.add_node(QUERY_TRANSFORMER_DEFAULT_RETRIEVAL, default_retrieval, metadata={"description": "Default retrieval strategy for simple queries", "type": "strategy_subgraph", "strategy": "default"})

workflow.add_node(QUERY_TRANSFORMER_PREPARE_OUTPUT, prepare_output, metadata={"description": "Prepares final output from selected strategy results", "type": "output_formatting_node", "criticality": "high"})

workflow.set_conditional_entry_point(
    route_to_transformer,
    {
        "multi_query": QUERY_TRANSFORMER_MULTI_QUERY,
        "decomposition": QUERY_TRANSFORMER_DECOMPOSITION,
        "step_back": QUERY_TRANSFORMER_STEP_BACK,
        "hyde": QUERY_TRANSFORMER_HYDE,
        "factual_strategy": QUERY_TRANSFORMER_FACTUAL_STRATEGY,
        "contextual_strategy": QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY,
        "default_retrieval": QUERY_TRANSFORMER_DEFAULT_RETRIEVAL,
    },
)

workflow.add_edge(QUERY_TRANSFORMER_MULTI_QUERY, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_DECOMPOSITION, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_STEP_BACK, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_HYDE, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_FACTUAL_STRATEGY, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_CONTEXTUAL_STRATEGY, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_DEFAULT_RETRIEVAL, QUERY_TRANSFORMER_PREPARE_OUTPUT)
workflow.add_edge(QUERY_TRANSFORMER_PREPARE_OUTPUT, END)

_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
query_transformer = workflow.compile(
    debug=True,
    name="query_transformation_strategy_router",
    interrupt_before=None,
    interrupt_after=None,
).with_config(
    {"recursion_limit": _RL}
)  # Optimized for performance in query transformation
