import os as _os

from langchain.chat_models import init_chat_model
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.config.node_names import (
    RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS,
    RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL,
    RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL,
    RETRIEVAL_SUBGRAPH_PLANNER,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.graph_retrieval import graph_tool_node
from src.core.agents.retrieval.keyword_retrieval import keyword_retriever
from src.core.agents.retrieval.vector_retrieval import vector_retriever
from src.schemas.state import RetrievalPlanModel, RetrievalSubgraphState


async def plan_retrieval_node(state: RetrievalSubgraphState, config: RunnableConfig) -> dict:
    # Access TypedDict values via mapping API (state is a plain dict at runtime)
    query = state["retrieval_query"]
    configuration = Configuration.from_runnable_config(config)
    # Build prompt for structured output planning
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                configuration.retrieval_planning_prompt + "\n\nWhen asked for output, respond with only the data, no commentary.",
            ),
            ("human", "Query: {query}"),
        ]
    )

    llm_struct = init_chat_model(configuration.retriever_worker_model, disable_streaming=configuration.disable_streaming).with_structured_output(RetrievalPlanModel)
    plan_model = await (prompt | llm_struct).ainvoke({"query": query})
    plan_dict = plan_model.model_dump() if hasattr(plan_model, "model_dump") else plan_model.dict()
    return {"retrieval_plan": plan_dict}


def ensemble_retrieval_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    """Retrieves documents using a dynamically configured ensemble retriever."""
    plan = state["retrieval_plan"]
    # Read planned knobs (k==0 means: disable that path)
    kw_weight = plan.get("keyword_weight", 0.5)
    vec_weight = plan.get("vector_weight", 0.5)
    vector_k = int(plan.get("vector_k", 10) or 0)
    keyword_k = int(plan.get("keyword_k", 10) or 0)
    rerank_k = plan.get("rerank_k", 5)
    query = state["retrieval_query"]
    # Build only enabled retrievers and align weights to avoid k=0 errors (e.g., Qdrant limit=0)
    retrievers = []
    weights = []
    if keyword_k > 0:
        retrievers.append(keyword_retriever.bind(top_k=keyword_k))
        weights.append(kw_weight)
    if vector_k > 0:
        retrievers.append(vector_retriever.bind(k=vector_k))
        weights.append(vec_weight)

    if not retrievers:
        return {"document_search_documents": []}

    ensemble_retriever = EnsembleRetriever(retrievers=retrievers, weights=weights or None)
    # Some EnsembleRetriever versions default k=0; force a safe positive top_k
    try:
        ensemble_retriever.k = max(1, vector_k, keyword_k)
    except Exception:
        pass
    compressor = CohereRerank(model="rerank-english-v3.0")
    compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)
    try:
        reranked_docs = compression_retriever.invoke(query)
    except Exception as e:
        # Graceful fallback if reranker is unavailable / rate-limited
        print(f"Cohere rerank unavailable or rate-limited; falling back to ensemble results. Error: {e}")
        reranked_docs = ensemble_retriever.invoke(query)
    final_docs = reranked_docs[:rerank_k]
    return {"document_search_documents": final_docs}


async def graph_retrieval_node(state: RetrievalSubgraphState, config: RunnableConfig) -> RetrievalSubgraphState:
    """Retrieves documents using graph search."""
    query = state["retrieval_query"]
    configuration = Configuration.from_runnable_config(config)
    documents = await graph_tool_node.ainvoke({"query": query, "conf": configuration})
    return {"graph_documents": documents}


def combine_documents_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    """Combines and deduplicates documents from all retrieval sources."""
    all_docs = state.get("document_search_documents", []) + state.get("graph_documents", [])
    return {"documents": all_docs}


workflow = StateGraph(state_schema=RetrievalSubgraphState, context_schema=Configuration)


workflow.add_node(
    node=RETRIEVAL_SUBGRAPH_PLANNER,
    action=plan_retrieval_node,
    destinations=[RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL, RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS],
    metadata={
        "description": "Plans retrieval strategy and k-parameters (set any k=0 to disable that method)",
        "type": "planning_node",
        "interaction": "internal",
        "criticality": "medium",
        "llm_powered": False,
        "strategy_selection": True,
        "expected_duration": "short",
        "analysis_types": ["query_complexity", "domain_requirements"],
        "dependencies": ["retrieval_query"],
        "outputs": ["retrieval_plan"],
    },
)

workflow.add_node(
    node=RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL,
    action=ensemble_retrieval_node,
    metadata={
        "description": "Performs ensemble document search across multiple vector retrievers",
        "type": "retrieval_node",
        "interaction": "vector_store",
        "criticality": "high",
        "parallel_capable": True,
        "retrieval_methods": ["semantic", "hybrid", "keyword"],
        "expected_duration": "medium",
        "performance_sensitive": True,
        "dependencies": ["retrieval_query", "vector_stores"],
        "outputs": ["retrieved_documents", "relevance_scores"],
    },
)

workflow.add_node(
    node=RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL,
    action=graph_retrieval_node,
    metadata={
        "description": "Performs graph-based knowledge retrieval using entity relationships",
        "type": "retrieval_node",
        "interaction": "knowledge_graph",
        "criticality": "high",
        "parallel_capable": True,
        "graph_methods": ["entity_traversal", "relationship_mining", "subgraph_extraction"],
        "expected_duration": "medium",
        "dependencies": ["retrieval_query", "knowledge_graph"],
        "outputs": ["graph_entities", "relationships", "contextual_info"],
    },
)

workflow.add_node(
    node=RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS,
    action=combine_documents_node,
    metadata={
        "description": "Combines, ranks, and filters documents from multiple retrieval sources",
        "type": "aggregation_node",
        "interaction": "internal",
        "criticality": "high",
        "ranking_algorithms": ["relevance", "diversity", "recency"],
        "deduplication": True,
        "expected_duration": "short",
        "dependencies": ["retrieved_documents", "graph_entities"],
        "outputs": ["ranked_documents", "combined_results"],
    },
)
workflow.set_entry_point(RETRIEVAL_SUBGRAPH_PLANNER)


def route_after_planning(state: RetrievalSubgraphState):
    """Select retrieval nodes based on k-values in the plan."""
    plan = state.get("retrieval_plan", {})
    vector_k = int(plan.get("vector_k", 0) or 0)
    keyword_k = int(plan.get("keyword_k", 0) or 0)
    graph_k = int(plan.get("graph_k", 0) or 0)

    nodes_to_run = []
    if (vector_k > 0) or (keyword_k > 0):
        nodes_to_run.append(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL)
    if graph_k > 0:
        nodes_to_run.append(RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL)

    return nodes_to_run if nodes_to_run else [RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS]


workflow.add_conditional_edges(
    source=RETRIEVAL_SUBGRAPH_PLANNER,
    path=route_after_planning,
)
workflow.add_edge(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL, RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS)
workflow.add_edge(RETRIEVAL_SUBGRAPH_GRAPH_RETRIEVAL, RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS)
workflow.add_edge(RETRIEVAL_SUBGRAPH_COMBINE_DOCUMENTS, END)


_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
retrieval_subgraph = workflow.compile(
    debug=True,
    name="retrieval_coordination_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
