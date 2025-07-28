from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.load import dumps, loads
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from langgraph.types import RunnableConfig, Send

from src.config.node_names import (
    MULTI_QUERY_DEDUPLICATE_DOCUMENTS,
    MULTI_QUERY_FORMAT_DOCUMENTS,
    MULTI_QUERY_GENERATE_QUERIES,
    MULTI_QUERY_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class MultiQueryState(QueryTransformerState):
    generated_queries: list[str] = []


# --- Nodes ---
def generate_queries_node(state: MultiQueryState, config: RunnableConfig) -> MultiQueryState:
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.multi_query_model)

    question = state["transformed_query"]
    prompt = ChatPromptTemplate.from_template(configuration.multi_query_perspectives_prompt)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.split("\n"))

    generated_queries = chain.invoke({"question": question})
    generated_queries = [q.strip() for q in generated_queries if q.strip()]

    if not generated_queries:
        raise ValueError("Failed to generate any valid queries from the input")

    return {"generated_queries": generated_queries}


def deduplicate_documents_node(state: RetrievalSubgraphState, config: RunnableConfig) -> MultiQueryState:
    retrieved_documents_lists = state["accumulated_documents"]

    flattened_docs_str = []

    for doc in retrieved_documents_lists:
        if isinstance(doc, Document):
            flattened_docs_str.append(dumps(doc))

    unique_docs_str = list(set(flattened_docs_str))

    unique_documents = []
    for doc_str in unique_docs_str:
        doc = loads(doc_str)
        if isinstance(doc, Document):
            unique_documents.append(doc)

    return {"accumulated_documents": unique_documents}


def format_documents_node(state: MultiQueryState) -> QueryTransformerState:
    formatted_string = format_docs(state["accumulated_documents"])
    return {"transformed_context": formatted_string}


workflow = StateGraph(state_schema=MultiQueryState, output_schema=QueryTransformerState, config_schema=Configuration)

workflow.add_node(
    node=MULTI_QUERY_GENERATE_QUERIES,
    action=generate_queries_node,
    destinations=[MULTI_QUERY_RETRIEVE_SUBGRAPH],
    metadata={
        "description": "Generates multiple perspective queries from original query for parallel retrieval",
        "type": "generation_node",
        "interaction": "internal",
        "criticality": "high",
        "llm_powered": True,
        "expected_duration": "2-4s",
        "model_type": "multi_query_model",
        "strategy": "multi_perspective_generation",
        "dependencies": ["transformed_query"],
        "outputs": ["generated_queries"],
        "parallel_trigger": True,
        "send_api_usage": True,
    },
)

workflow.add_node(
    node=MULTI_QUERY_RETRIEVE_SUBGRAPH,
    action=retrieval_subgraph,
    metadata={
        "description": "Parallel retrieval subgraph executed for each generated query perspective",
        "type": "retrieval_subgraph",
        "interaction": "external_apis",
        "criticality": "high",
        "parallel_execution": True,
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "dependencies": ["retrieval_query"],
        "outputs": ["documents"],
        "context": "multi_perspective_retrieval",
        "async_execution": True,
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
        "dependencies": ["accumulated_documents"],
        "outputs": ["unique_documents"],
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
        "dependencies": ["accumulated_documents"],
        "outputs": ["transformed_context"],
        "final_output": True,
    },
)

workflow.set_entry_point(MULTI_QUERY_GENERATE_QUERIES)


def route_from_generate_queries(state: MultiQueryState) -> list[Send]:
    """
    Route to multiple retrieval subgraph invocations based on generated queries.
    Uses Send API for parallel execution of retrieval operations.
    """
    queries = state["generated_queries"]
    sends = [Send(MULTI_QUERY_RETRIEVE_SUBGRAPH, {"retrieval_query": q}) for q in queries]
    return sends


workflow.add_conditional_edges(source=MULTI_QUERY_GENERATE_QUERIES, path=route_from_generate_queries, path_map=None)  # Direct Send API routing, no path mapping needed

# After all parallel retrieval runs are complete, they are joined at the next node
workflow.add_edge(start_key=MULTI_QUERY_RETRIEVE_SUBGRAPH, end_key=MULTI_QUERY_DEDUPLICATE_DOCUMENTS)

workflow.add_edge(start_key=MULTI_QUERY_DEDUPLICATE_DOCUMENTS, end_key=MULTI_QUERY_FORMAT_DOCUMENTS)

workflow.add_edge(start_key=MULTI_QUERY_FORMAT_DOCUMENTS, end_key=END)

multi_query = workflow.compile(debug=True, name="multi_query_parallel_retrieval_strategy", interrupt_before=None, interrupt_after=None, checkpointer=None)
