from typing import Any, Dict, List

from langchain.chat_models import init_chat_model
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from src.config.node_names import (
    RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS,
    RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL,
    RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL,
    RETRIEVAL_SUBGRAPH_PLANNER,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.graph_retrieval import graph_tool_node
from src.core.agents.retrieval.keyword_retrieval import keyword_retriever

# We need the vector_store object to dynamically create retrievers with different `k` values
from src.core.agents.retrieval.vector_retrieval import vector_retriever
from src.schemas.core_types import AgentState


class DocumentSearchParamsModel(BaseModel):
    weights: Dict[str, float]
    vector_k: int
    keyword_k: int
    ensemble_k: int


class RetrievalPlanModel(BaseModel):
    methods: List[str]
    doc_search_params: DocumentSearchParamsModel
    rerank_k: int


class RetrievalSubgraphState(AgentState):
    """State for the retrieval subgraph."""

    # The `retrieval_query` from AgentState is used as the input query.
    retrieval_query: str = ""
    retrieval_plan: Dict[str, Any] = {}
    graph_documents: List[Document] = []
    document_search_documents: List[Document] = []
    documents: List[Document] = []  # Final combined list


def plan_retrieval_node(state: AgentState, config: Configuration) -> dict:
    query = state.retrieval_query
    llm = init_chat_model(config.retriever_worker_model)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.retrieval_planning_prompt),
            ("human", "Query: {query}"),
        ]
    ).with_structured_output(RetrievalPlanModel)
    chain = prompt | llm

    plan: RetrievalPlanModel = chain.invoke({"query": query})
    return {"retrieval_plan": plan.dict()}


def ensemble_retrieval_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    """Retrieves documents using a dynamically configured ensemble retriever."""
    plan = state["retrieval_plan"]
    params = plan.get("doc_search_params", {})
    weights_dict = params.get("weights", {"keyword": 0.5, "vector": 0.5})
    weights = [weights_dict.get("keyword", 0.5), weights_dict.get("vector", 0.5)]
    vector_k = params.get("vector_k", 10)
    keyword_k = params.get("keyword_k", 10)
    params.get("ensemble_k", 10)
    rerank_k = plan.get("rerank_k", 5)
    query = state["retrieval_query"]

    # Create a new vector retriever with the specified `k`

    ensemble_retriever = EnsembleRetriever(retrievers=[keyword_retriever.bind(top_k=keyword_k), vector_retriever.bind(k=vector_k)], weights=weights)
    compressor = CohereRerank(model="rerank-english-v3.0")
    compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)
    reranked_docs = compression_retriever.invoke(query)
    final_docs = reranked_docs[:rerank_k]
    return {"document_search_documents": final_docs}


def graph_retrieval_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    """Retrieves documents using graph search."""
    query = state["retrieval_query"]
    documents = graph_tool_node.invoke(query, state=state)
    return {"graph_documents": documents}


def combine_documents_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    """Combines and deduplicates documents from all retrieval sources."""
    all_docs = state.get("document_search_documents", []) + state.get("graph_documents", [])
    return {"documents": all_docs}


# --- Graph Definition ---

workflow = StateGraph(RetrievalSubgraphState)

workflow.add_node(RETRIEVAL_SUBGRAPH_PLANNER, plan_retrieval_node)
workflow.add_node(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, ensemble_retrieval_node)
workflow.add_node(RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL, graph_retrieval_node)
workflow.add_node(RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS, combine_documents_node)
workflow.set_entry_point(RETRIEVAL_SUBGRAPH_PLANNER)


def route_after_planning(state: RetrievalSubgraphState):
    """Return a list of nodes to run in parallel based on the plan."""
    methods = state.get("retrieval_plan", {}).get("methods", [])

    nodes_to_run = []
    if "document_search" in methods:
        nodes_to_run.append(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL)
    if "graph_search" in methods:
        nodes_to_run.append(RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL)

    return nodes_to_run if nodes_to_run else [RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS]


workflow.add_conditional_edges(RETRIEVAL_SUBGRAPH_PLANNER, route_after_planning)

workflow.add_edge(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS)
workflow.add_edge(RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL, RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS)
workflow.add_edge(RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS, END)
# Compile the graph into a runnable object
retrieval_subgraph = workflow.compile()
