from functools import partial

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config.constant import MODEL_NAME
from src.core.agents.context_processor import context_processor_agent
from src.core.agents.generator import generator_agent
from src.core.agents.multi_step_reasoning import multi_step_reasoning_agent
from src.core.agents.query_transformer import query_transformer_agent
from src.core.agents.query_understanding import query_understanding_agent
from src.core.agents.retrieval import retrieval_agent
from src.core.agents.retrieval_strategy import retrieval_strategy_agent
from src.core.agents.state import AgentState
from src.core.agents.summarizer import summarizer_agent  # Import the new summarizer agent
from src.core.agents.validation import validation_agent


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
    summarizer_agent_with_model = partial(summarizer_agent, model=model)  # New summarizer partial

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("query_understanding", query_understanding_agent_with_model)
    workflow.add_node("retrieval_strategy", retrieval_strategy_agent_with_model)
    workflow.add_node("query_transformer", query_transformer_agent)
    workflow.add_node("retrieval", retrieval_agent)
    workflow.add_node("context_processor", context_processor_agent)
    workflow.add_node("generator", generator_agent_with_model)
    workflow.add_node("validation", validation_agent_with_model)
    workflow.add_node("multi_step_reasoning", multi_step_reasoning_agent_with_model)
    workflow.add_node("summarizer", summarizer_agent_with_model)  # New summarizer node
    workflow.add_node(
        "error",
        lambda state: {"answer": "I'm sorry, but I encountered an error. Please try again."},
    )

    # Add edges
    workflow.set_entry_point("query_understanding")
    workflow.add_edge("query_transformer", "retrieval")
    workflow.add_edge("retrieval", "context_processor")
    workflow.add_edge("context_processor", "generator")
    workflow.add_edge("generator", "validation")

    # Add conditional edges from query_understanding
    def route_from_query_understanding(state: AgentState):
        if state.error:
            return "error"
        # Always route to check_history_length first
        return "check_history_length"

    workflow.add_conditional_edges(
        "query_understanding",
        route_from_query_understanding,
        {
            "check_history_length": "check_history_length",
            "error": "error",
        },
    )

    # New node to check history length and route to summarizer or next step
    def check_history_length(state: AgentState):
        # Define a threshold for summarization (e.g., 10 messages)
        # Each user query and agent response counts as one message.
        # So, 10 messages means 5 user turns and 5 agent turns.
        SUMMARY_THRESHOLD = 10
        if len(state.chat_history) >= SUMMARY_THRESHOLD:
            return "summarize"
        else:
            # Route to the original next step based on intent
            if state.intent == "document request":
                return "retrieval_strategy"
            elif state.intent in ["structured_graph_query", "statistical_graph_query"]:
                return "retrieval"
            else:
                return "generator"

    workflow.add_node("check_history_length", check_history_length)
    workflow.add_conditional_edges(
        "check_history_length",
        check_history_length,
        {
            "summarize": "summarizer",
            "retrieval_strategy": "retrieval_strategy",
            "retrieval": "retrieval",
            "generator": "generator",
            "error": "error",
        },
    )

    # Add conditional edges from summarizer
    def route_from_summarizer(state: AgentState):
        if state.error:
            return "error"
        # After summarization, route to the original next step based on intent
        if state.intent == "document request":
            return "retrieval_strategy"
        elif state.intent in ["structured_graph_query", "statistical_graph_query"]:
            return "retrieval"
        else:
            return "generator"

    workflow.add_conditional_edges(
        "summarizer",
        route_from_summarizer,
        {
            "retrieval_strategy": "retrieval_strategy",
            "retrieval": "retrieval",
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


app = create_graph()
