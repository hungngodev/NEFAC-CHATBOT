from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.config.node_names import MEMORY_SUMMARIZER_NODE, RESEARCH_CLARIFY_WITH_USER, RESEARCH_FINAL_REPORT_GENERATION, RESEARCH_SUPERVISOR, RESEARCH_WRITE_RESEARCH_BRIEF
from src.config.settings import Configuration
from src.core.agents.generation.final_report_generation import final_report_generation
from src.core.agents.memory.summarizer import summarizer
from src.core.agents.query_understanding.clarification import clarify_with_user
from src.core.agents.query_understanding.write_research_brief import write_research_brief
from src.core.agents.supervisor.supervisor import supervisor_subgraph
from src.schemas.state import AgentInputState, AgentState


def route_after_clarification(state: AgentState) -> Literal["write_research_brief"]:
    """Route to research brief writing after clarification."""
    return RESEARCH_WRITE_RESEARCH_BRIEF


def make_graph():
    """Factory function to create and return the deep researcher graph."""
    deep_researcher_builder = StateGraph(AgentState, input=AgentInputState, config_schema=Configuration)
    deep_researcher_builder.add_node(RESEARCH_CLARIFY_WITH_USER, clarify_with_user)
    deep_researcher_builder.add_node(RESEARCH_WRITE_RESEARCH_BRIEF, write_research_brief)
    deep_researcher_builder.add_node(RESEARCH_SUPERVISOR, supervisor_subgraph)
    deep_researcher_builder.add_node(RESEARCH_FINAL_REPORT_GENERATION, final_report_generation)
    deep_researcher_builder.add_node(MEMORY_SUMMARIZER_NODE, summarizer)

    deep_researcher_builder.add_edge(START, MEMORY_SUMMARIZER_NODE)
    deep_researcher_builder.add_edge(MEMORY_SUMMARIZER_NODE, RESEARCH_CLARIFY_WITH_USER)
    deep_researcher_builder.add_conditional_edges(RESEARCH_CLARIFY_WITH_USER, route_after_clarification)
    deep_researcher_builder.add_edge(RESEARCH_WRITE_RESEARCH_BRIEF, RESEARCH_SUPERVISOR)
    deep_researcher_builder.add_edge(RESEARCH_SUPERVISOR, RESEARCH_FINAL_REPORT_GENERATION)
    deep_researcher_builder.add_edge(RESEARCH_FINAL_REPORT_GENERATION, END)

    return deep_researcher_builder.compile()


# For backward compatibility
deep_researcher = make_graph()
