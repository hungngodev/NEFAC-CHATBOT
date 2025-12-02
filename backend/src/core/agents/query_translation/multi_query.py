"""Multi‑query: generate queries, retrieve, dedup, format."""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    MULTI_QUERY_ACCUMULATE,
    MULTI_QUERY_FORMAT_DOCUMENTS,
    MULTI_QUERY_GENERATE_QUERIES,
    MULTI_QUERY_NEXT,
    MULTI_QUERY_RETRIEVE_SUBGRAPH,
    QUERY_TRANSFORMER_MULTI_QUERY,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState
from src.utils.debug import get_debug_mode
from src.utils.model_factory import init_model


# --- Subgraph State ---
class MultiQueryState(QueryTransformerState):
    generated_queries: list[str] = []
    current_index: int = 0


# --- Nodes ---
async def generate_queries_node(state: MultiQueryState, config: RunnableConfig) -> MultiQueryState:
    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.query_transformer_model, disable_streaming=configuration.disable_streaming, node_name=QUERY_TRANSFORMER_MULTI_QUERY)

    question = state["transformed_query"]
    prompt = ChatPromptTemplate.from_template(configuration.multi_query_perspectives_prompt)
    chain = prompt | llm | StrOutputParser()

    output = await chain.ainvoke({"question": question})
    generated_queries = [q.strip() for q in str(output).split("\n") if q.strip()]
    if not generated_queries:
        raise ValueError("Failed to generate any valid queries from the input")

    return {"generated_queries": generated_queries}


def next_query_node(state: MultiQueryState) -> MultiQueryState:
    """Select the next generated query for retrieval, if any remain."""
    idx = state.get("current_index", 0)
    queries = state.get("generated_queries", [])
    if idx >= len(queries):
        return {}
    return {"retrieval_query": queries[idx]}


def advance_index_node(state: MultiQueryState) -> MultiQueryState:
    """Advance the query index. Documents are accumulated automatically via reducer."""
    return {
        "current_index": state.get("current_index", 0) + 1,
    }


def format_documents_node(state: MultiQueryState) -> QueryTransformerState:
    formatted_string = format_docs(state.get("documents", []))
    return {"transformed_context": formatted_string}


def route_after_accumulate(state: MultiQueryState) -> str:
    return MULTI_QUERY_NEXT if state.get("current_index", 0) < len(state.get("generated_queries", [])) else MULTI_QUERY_FORMAT_DOCUMENTS


workflow = StateGraph(state_schema=MultiQueryState, output_schema=QueryTransformerState, context_schema=Configuration)

workflow.add_node(
    node=MULTI_QUERY_GENERATE_QUERIES,
    action=generate_queries_node,
    destinations=[MULTI_QUERY_NEXT],
    metadata={
        "description": "Generates multiple perspective queries from original query",
        "type": "generation_node",
        "interaction": "internal",
        "criticality": "high",
        "llm_powered": True,
        "expected_duration": "2-4s",
        "model_type": "multi_query_model",
        "strategy": "multi_perspective_generation",
        "dependencies": ["transformed_query"],
        "outputs": ["generated_queries"],
    },
)


workflow.add_node(
    node=MULTI_QUERY_NEXT,
    action=next_query_node,
    destinations=[MULTI_QUERY_RETRIEVE_SUBGRAPH],
    metadata={
        "description": "Sets the next generated query as retrieval input",
        "type": "control_node",
        "dependencies": ["generated_queries", "current_index"],
        "outputs": ["retrieval_query"],
    },
)

workflow.add_node(
    node=MULTI_QUERY_RETRIEVE_SUBGRAPH,
    action=retrieval_subgraph,
    destinations=[MULTI_QUERY_ACCUMULATE],
    metadata={
        "description": "Retrieval subgraph executed per generated query (sequential)",
        "type": "retrieval_subgraph",
        "interaction": "external_apis",
        "criticality": "high",
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "dependencies": ["retrieval_query"],
        "outputs": ["documents"],
        "context": "multi_perspective_retrieval",
    },
)

workflow.add_node(
    node=MULTI_QUERY_ACCUMULATE,
    destinations=[MULTI_QUERY_NEXT, MULTI_QUERY_FORMAT_DOCUMENTS],
    action=advance_index_node,
    metadata={
        "description": "Accumulates documents from this query into the running set",
        "type": "processing_node",
        "dependencies": ["documents", "current_index"],
        "outputs": ["collected_documents", "current_index"],
    },
)


workflow.add_node(
    node=MULTI_QUERY_FORMAT_DOCUMENTS,
    action=format_documents_node,
    destinations=[END],
    metadata={
        "description": "Formats deduplicated documents into final transformed context string",
        "type": "formatting_node",
        "interaction": "internal",
        "criticality": "low",
        "expected_duration": "0.5-1s",
        "formatting_method": "document_concatenation",
        "dependencies": ["collected_documents"],
        "outputs": ["transformed_context"],
        "final_output": True,
    },
)

workflow.add_edge(START, MULTI_QUERY_GENERATE_QUERIES)
workflow.add_edge(MULTI_QUERY_GENERATE_QUERIES, MULTI_QUERY_NEXT)
workflow.add_edge(MULTI_QUERY_NEXT, MULTI_QUERY_RETRIEVE_SUBGRAPH)
workflow.add_edge(MULTI_QUERY_RETRIEVE_SUBGRAPH, MULTI_QUERY_ACCUMULATE)
workflow.add_conditional_edges(MULTI_QUERY_ACCUMULATE, route_after_accumulate)
workflow.add_edge(MULTI_QUERY_FORMAT_DOCUMENTS, END)

multi_query = workflow.compile(debug=get_debug_mode(), name="multi_query_sequential_retrieval_strategy", interrupt_before=None, interrupt_after=None, checkpointer=None)
