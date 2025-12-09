import os as _os

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
from src.config.prompt.retrieval import (
    GRAPH_SEARCH_GUIDELINE,
    GRAPH_SEARCH_KNOB,
    GRAPH_SEARCH_METHOD,
    GRAPH_SEARCH_PARAM,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.graph_retrieval import graph_tool_node
from src.core.agents.retrieval.keyword_retrieval import keyword_retriever
from src.core.agents.retrieval.vector_retrieval import vector_retriever
from src.schemas.state import RetrievalPlanModel, RetrievalSubgraphState
from src.utils.debug import get_debug_mode
from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event
from src.utils.model_factory import init_model


async def plan_retrieval_node(state: RetrievalSubgraphState, config: RunnableConfig) -> dict:
    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Planning retrieval strategy..."})
    query = state["retrieval_query"]
    configuration = Configuration.from_runnable_config(config)

    # Dynamically construct the prompt based on graph search availability
    if configuration.enable_graph_search:
        system_prompt = configuration.retrieval_planning_prompt.format(
            graph_knob=GRAPH_SEARCH_KNOB,
            graph_method=GRAPH_SEARCH_METHOD,
            graph_guideline=GRAPH_SEARCH_GUIDELINE,
            graph_param=GRAPH_SEARCH_PARAM,
        )
    else:
        system_prompt = configuration.retrieval_planning_prompt.format(
            graph_knob="",
            graph_method="",
            graph_guideline="",
            graph_param="",
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt + "\n\nWhen asked for output, respond with only the data, no commentary.",
            ),
            ("human", "Query: {query}"),
        ]
    )

    # Initialize the retrieval planner model
    llm_struct = init_model(configuration.retrieval_planner_model, disable_streaming=configuration.disable_streaming, node_name=RETRIEVAL_SUBGRAPH_PLANNER).with_structured_output(RetrievalPlanModel)
    plan_model = await (prompt | llm_struct).ainvoke({"query": query})
    plan_dict = plan_model.model_dump() if hasattr(plan_model, "model_dump") else plan_model.dict()
    return {"retrieval_plan": plan_dict}


def ensemble_retrieval_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Searching documents..."})
    plan = state["retrieval_plan"]
    kw_weight = plan.get("keyword_weight", 0.5)
    vec_weight = plan.get("vector_weight", 0.5)
    vector_k = int(plan.get("vector_k", 10) or 0)
    keyword_k = int(plan.get("keyword_k", 10) or 0)
    rerank_k = plan.get("rerank_k", 5)
    query = state["retrieval_query"]
    retrievers = []
    weights = []
    if keyword_k > 0:
        retrievers.append(keyword_retriever.bind(k=keyword_k))
        weights.append(kw_weight)
    if vector_k > 0:
        retrievers.append(vector_retriever.bind(k=vector_k))
        weights.append(vec_weight)

    if not retrievers:
        return {"document_search_documents": []}

    ensemble_retriever = EnsembleRetriever(retrievers=retrievers, weights=weights or None)
    compressor = CohereRerank(model="rerank-english-v3.0")
    compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=ensemble_retriever)
    reranked_docs = compression_retriever.invoke(query)
    final_docs = reranked_docs[:rerank_k]
    return {"document_search_documents": final_docs}


async def graph_retrieval_node(state: RetrievalSubgraphState, config: RunnableConfig) -> RetrievalSubgraphState:
    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Querying knowledge graph..."})
    query = state["retrieval_query"]
    configuration = Configuration.from_runnable_config(config)
    documents = await graph_tool_node.ainvoke({"query": query, "conf": configuration})
    return {"graph_documents": documents}


def combine_documents_node(state: RetrievalSubgraphState) -> RetrievalSubgraphState:
    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Combining retrieved documents..."})
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


def route_after_planning(state: RetrievalSubgraphState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    plan = state.get("retrieval_plan", {})
    vector_k = int(plan.get("vector_k", 0) or 0)
    keyword_k = int(plan.get("keyword_k", 0) or 0)
    graph_k = int(plan.get("graph_k", 0) or 0)

    nodes_to_run = []
    if (vector_k > 0) or (keyword_k > 0):
        nodes_to_run.append(RETRIEVAL_SUBGRAPH_ENSEMBLE_RETRIEVAL)
    if graph_k > 0 and configuration.enable_graph_search:
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
    debug=get_debug_mode(),
    name="retrieval_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
