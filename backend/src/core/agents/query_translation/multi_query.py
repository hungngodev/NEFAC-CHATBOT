"""Multi‑query: generate queries, retrieve, dedup, format."""

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    MULTI_QUERY_ACCUMULATE,
    MULTI_QUERY_DEDUPLICATE_DOCUMENTS,
    MULTI_QUERY_FORMAT_DOCUMENTS,
    MULTI_QUERY_GENERATE_QUERIES,
    MULTI_QUERY_NEXT,
    MULTI_QUERY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class MultiQueryState(QueryTransformerState):
    generated_queries: list[str] = []
    current_index: int = 0
    collected_documents: list[Document] = []


# --- Nodes ---
async def generate_queries_node(state: MultiQueryState, config: RunnableConfig) -> MultiQueryState:
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.multi_query_model, disable_streaming=configuration.disable_streaming)

    question = state["transformed_query"]
    prompt = ChatPromptTemplate.from_template(configuration.multi_query_perspectives_prompt)
    chain = prompt | llm | StrOutputParser()

    output = await chain.ainvoke({"question": question})
    generated_queries = [q.strip() for q in str(output).split("\n") if q.strip()]
    if not generated_queries:
        raise ValueError("Failed to generate any valid queries from the input")

    return {"generated_queries": generated_queries}


def deduplicate_documents_node(state: MultiQueryState, config: RunnableConfig) -> MultiQueryState:
    collected = state.get("collected_documents", [])
    unique_serialized = {dumps(d) for d in collected if isinstance(d, Document)}
    unique_documents = [loads(s) for s in unique_serialized if isinstance(loads(s), Document)]
    return {"collected_documents": unique_documents}


def format_documents_node(state: MultiQueryState) -> QueryTransformerState:
    formatted_string = format_docs(state.get("collected_documents", []))
    return {"transformed_context": formatted_string}


workflow = StateGraph(state_schema=MultiQueryState, output_schema=QueryTransformerState, context_schema=Configuration)

workflow.add_node(
    node=MULTI_QUERY_GENERATE_QUERIES,
    action=generate_queries_node,
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


def next_query_node(state: MultiQueryState) -> MultiQueryState:
    """Select the next generated query for retrieval, if any remain."""
    idx = state.get("current_index", 0)
    queries = state.get("generated_queries", [])
    if idx >= len(queries):
        return {}
    return {"retrieval_query": queries[idx]}


def accumulate_documents_node(state: MultiQueryState) -> MultiQueryState:
    """Append newly retrieved documents and advance the query index."""
    docs = state.get("documents", [])
    collected = state.get("collected_documents", []) + docs
    return {
        "collected_documents": collected,
        "current_index": state.get("current_index", 0) + 1,
    }


workflow.add_node(
    node=MULTI_QUERY_NEXT,
    action=next_query_node,
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
    action=accumulate_documents_node,
    metadata={
        "description": "Accumulates documents from this query into the running set",
        "type": "processing_node",
        "dependencies": ["documents", "current_index"],
        "outputs": ["collected_documents", "current_index"],
    },
)

workflow.add_node(
    node=MULTI_QUERY_DEDUPLICATE_DOCUMENTS,
    action=deduplicate_documents_node,
    metadata={
        "description": "Deduplicates and merges documents from parallel retrieval operations",
        "type": "processing_node",
        "interaction": "internal",
        "criticality": "medium",
        "expected_duration": "1-3s",
        "processing_method": "document_deduplication",
        "dependencies": ["collected_documents"],
        "outputs": ["collected_documents"],
        "optimization": "hash_based_deduplication",
        "merge_strategy": "content_aware",
    },
)

workflow.add_node(
    node=MULTI_QUERY_FORMAT_DOCUMENTS,
    action=format_documents_node,
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

workflow.set_entry_point(MULTI_QUERY_GENERATE_QUERIES)
workflow.add_edge(MULTI_QUERY_GENERATE_QUERIES, MULTI_QUERY_NEXT)
workflow.add_edge(MULTI_QUERY_NEXT, MULTI_QUERY_RETRIEVE_SUBGRAPH)
workflow.add_edge(MULTI_QUERY_RETRIEVE_SUBGRAPH, MULTI_QUERY_ACCUMULATE)


def route_after_accumulate(state: MultiQueryState) -> str:
    if state.get("current_index", 0) < len(state.get("generated_queries", [])):
        return MULTI_QUERY_NEXT
    else:
        return MULTI_QUERY_DEDUPLICATE_DOCUMENTS


workflow.add_conditional_edges(source=MULTI_QUERY_ACCUMULATE, path=route_after_accumulate)

workflow.add_edge(start_key=MULTI_QUERY_DEDUPLICATE_DOCUMENTS, end_key=MULTI_QUERY_FORMAT_DOCUMENTS)

workflow.add_edge(start_key=MULTI_QUERY_FORMAT_DOCUMENTS, end_key=END)

multi_query = workflow.compile(debug=True, name="multi_query_sequential_retrieval_strategy", interrupt_before=None, interrupt_after=None, checkpointer=None)
