from functools import partial

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from llm.constant import MODEL_NAME

from .generator import generator_agent
from .multi_step_reasoning import multi_step_reasoning_agent
from .query_transformer import query_transformer_agent
from .query_understanding import query_understanding_agent
from .retrieval import retrieval_agent
from .retrieval_strategy import retrieval_strategy_agent
from .state import AgentState
from .validation import validation_agent


def create_graph():
    """
    Creates the LangGraph workflow.
    """
    model = ChatOpenAI(model=MODEL_NAME, streaming=True)

    # Create partial functions with the model
    query_understanding_agent_with_model = partial(query_understanding_agent, model=model)
    retrieval_strategy_agent_with_model = partial(retrieval_strategy_agent, model=model)
    generator_agent_with_model = partial(generator_agent, model=model)
    validation_agent_with_model = partial(validation_agent, model=model)
    multi_step_reasoning_agent_with_model = partial(multi_step_reasoning_agent, model=model)

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("query_understanding", query_understanding_agent_with_model)
    workflow.add_node("retrieval_strategy", retrieval_strategy_agent_with_model)
    workflow.add_node("query_transformer", query_transformer_agent)
    workflow.add_node("retrieval", retrieval_agent)
    workflow.add_node("generator", generator_agent_with_model)
    workflow.add_node("validation", validation_agent_with_model)
    workflow.add_node("multi_step_reasoning", multi_step_reasoning_agent_with_model)
    workflow.add_node(
        "error",
        lambda state: {"answer": "I'm sorry, but I encountered an error. Please try again."},
    )

    # Add edges
    workflow.set_entry_point("query_understanding")
    workflow.add_edge("query_transformer", "retrieval")
    workflow.add_edge("retrieval", "generator")
    workflow.add_edge("generator", "validation")

    # Add conditional edges from query_understanding
    def route_from_query_understanding(state: AgentState):
        if state.error:
            return "error"
        if state.intent == "document request":
            return "retrieval_strategy"
        else:
            return "generator"

    workflow.add_conditional_edges(
        "query_understanding",
        route_from_query_understanding,
        {
            "retrieval_strategy": "retrieval_strategy",
            "generator": "generator",
            "error": "error",
        },
    )

    # Add conditional edges from retrieval_strategy
    def route_from_retrieval_strategy(state: AgentState):
        if state.error:
            return "error"
        if state.retrieval_method == "multi-step":
            return "multi_step_reasoning"
        else:
            return "query_transformer"

    workflow.add_conditional_edges(
        "retrieval_strategy",
        route_from_retrieval_strategy,
        {
            "multi_step_reasoning": "multi_step_reasoning",
            "query_transformer": "query_transformer",
            "error": "error",
        },
    )

    # Add conditional edges from multi_step_reasoning
    workflow.add_edge("multi_step_reasoning", "generator")

    # Add conditional edges from validation
    def validation_router(state: AgentState):
        if state.error:
            return "error"
        if state.validation and state.validation.get("is_valid"):
            return END
        else:
            return "retrieval_strategy"  # Loop back for refinement

    workflow.add_conditional_edges(
        "validation",
        validation_router,
        {
            END: END,
            "retrieval_strategy": "retrieval_strategy",
            "error": "error",
        },
    )

    workflow.add_edge("error", END)

    return workflow.compile()
