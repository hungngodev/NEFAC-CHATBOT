import os as _os

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from src.config.node_names import (
    CLEANUP_NODE,
    MEMORY_SUMMARIZER_NODE,
    QUICK_AGENT_NODE,
    RESEARCH_CLARIFY_WITH_USER,
    RESEARCH_FINAL_REPORT_GENERATION,
    RESEARCH_SUPERVISOR,
    RESEARCH_WRITE_RESEARCH_BRIEF,
)
from src.config.settings import Configuration
from src.core.agents.generation.final_report_generation import final_report_generation
from src.core.agents.generation.generate_navigation_guide import generate_navigation_guide
from src.core.agents.memory.summarizer import summarizer
from src.core.agents.query_understanding.clarification import clarify_with_user
from src.core.agents.query_understanding.write_research_brief import write_research_brief
from src.core.agents.quick_agent.quick_agent import quick_agent_subgraph
from src.core.agents.supervisor.supervisor import supervisor_subgraph
from src.schemas.state import AgentInputState, AgentState
from src.utils.debug import get_debug_mode

# Node name for librarian mode final output
NAVIGATION_GUIDE_GENERATION = "navigation_guide_generation"

deep_researcher_builder = StateGraph(state_schema=AgentState, input_schema=AgentInputState, output_schema=AgentState, context_schema=Configuration)


deep_researcher_builder.add_node(
    node=RESEARCH_CLARIFY_WITH_USER,
    action=clarify_with_user,
    destinations=[RESEARCH_WRITE_RESEARCH_BRIEF, END],
    metadata={
        "description": "Clarifies user research intent and determines if additional information is needed",
        "type": "decision_node",
        "interaction": "user_facing",
        "criticality": "high",
        "llm_powered": True,
        "conditional_routing": True,
        "expected_duration": "medium",
        # Uses summarized messages if present; otherwise raw messages
        "dependencies": ["messages", "summarized_messages"],
        "outputs": ["clarified_intent", "routing_decision"],
    },
    retry_policy=None,
    cache_policy=None,
)

deep_researcher_builder.add_node(
    node=RESEARCH_WRITE_RESEARCH_BRIEF,
    action=write_research_brief,
    metadata={
        "description": "Generates a comprehensive research brief based on clarified user intent",
        "type": "generation_node",
        "interaction": "internal",
        "criticality": "high",
        "llm_powered": True,
        "expected_duration": "medium",
        "dependencies": ["clarified_intent"],
        "outputs": ["research_brief", "research_scope"],
    },
    retry_policy=None,
    cache_policy=None,
)

deep_researcher_builder.add_node(
    node=RESEARCH_SUPERVISOR,
    action=supervisor_subgraph,
    metadata={
        "description": "Coordinates research activities and manages research team workflow",
        "type": "coordination_subgraph",
        "interaction": "internal",
        "criticality": "critical",
        "parallel_capable": True,
        "command_routing": True,
        "expected_duration": "long",
        "dependencies": ["research_brief"],
        "outputs": ["research_results", "notes", "raw_notes"],
    },
    retry_policy=None,
    cache_policy=None,
)

deep_researcher_builder.add_node(
    node=RESEARCH_FINAL_REPORT_GENERATION,
    action=final_report_generation,
    metadata={
        "description": "Synthesizes all research findings into a final comprehensive report",
        "type": "generation_node",
        "interaction": "user_facing",
        "criticality": "high",
        "llm_powered": True,
        "expected_duration": "medium",
        "dependencies": ["research_results", "notes"],
        "outputs": ["final_report"],
        "mode": "research",
    },
    retry_policy=None,
    cache_policy=None,
)

# Librarian mode: Navigation guide generation instead of research report
deep_researcher_builder.add_node(
    node=NAVIGATION_GUIDE_GENERATION,
    action=generate_navigation_guide,
    metadata={
        "description": "Creates a resource navigation guide instead of synthesizing answers (librarian mode)",
        "type": "generation_node",
        "interaction": "user_facing",
        "criticality": "high",
        "llm_powered": True,
        "expected_duration": "medium",
        "dependencies": ["research_results", "notes"],
        "outputs": ["final_report"],
        "mode": "librarian",
    },
    retry_policy=None,
    cache_policy=None,
)

deep_researcher_builder.add_node(
    node=MEMORY_SUMMARIZER_NODE,
    action=summarizer,
    metadata={
        "description": "Maintains short-term conversation summary (no user-facing reply)",
        "type": "preprocessing_node",
        "interaction": "internal",
        "criticality": "medium",
        "llm_powered": True,
        "expected_duration": "short",
        # Reads chat history from messages; updates 'summary' and provides 'summarized_messages'
        "dependencies": ["messages"],
        "outputs": ["summary", "summarized_messages"],
    },
    retry_policy=None,
    cache_policy=None,
)

deep_researcher_builder.add_node(
    node=QUICK_AGENT_NODE,
    action=quick_agent_subgraph,
    metadata={
        "description": "Quick QA agent subgraph for fast, direct answers",
        "type": "agent_subgraph",
        "interaction": "tool_calling",
        "criticality": "high",
        "llm_powered": True,
        "tool_binding": True,
        "expected_duration": "short",
        "max_iterations": 5,
        "dependencies": ["messages", "available_tools"],
        "outputs": ["final_report", "messages"],
    },
)


def cleanup_node(state: AgentState) -> dict:
    """Cleans up state at the end of a turn."""
    return {
        "final_documents": {"type": "override", "value": []},
        "supervisor_messages": {"type": "override", "value": []},
    }


deep_researcher_builder.add_node(
    node=CLEANUP_NODE,
    action=cleanup_node,
    metadata={
        "description": "Cleans up state (documents, internal messages) at the end of a turn",
        "type": "cleanup_node",
        "interaction": "internal",
        "criticality": "medium",
        "expected_duration": "short",
        "dependencies": [],
        "outputs": ["final_documents", "supervisor_messages"],
    },
)


def route_after_summarizer(state: AgentState, config: RunnableConfig) -> str:
    """Route to quick agent or clarification based on research_mode."""
    configurable = Configuration.from_runnable_config(config)
    if configurable.research_mode == "quick":
        return QUICK_AGENT_NODE
    return RESEARCH_CLARIFY_WITH_USER


def route_after_supervisor(state: AgentState, config: RunnableConfig) -> str:
    """Route to appropriate final output based on librarian_mode.

    In librarian_mode: route to navigation guide generation
    In research_mode: route to final report generation
    """
    configurable = Configuration.from_runnable_config(config)
    if configurable.librarian_mode:
        return NAVIGATION_GUIDE_GENERATION
    return RESEARCH_FINAL_REPORT_GENERATION


deep_researcher_builder.add_edge(START, MEMORY_SUMMARIZER_NODE)
deep_researcher_builder.add_conditional_edges(
    MEMORY_SUMMARIZER_NODE,
    route_after_summarizer,
    {
        QUICK_AGENT_NODE: QUICK_AGENT_NODE,
        RESEARCH_CLARIFY_WITH_USER: RESEARCH_CLARIFY_WITH_USER,
    },
)
deep_researcher_builder.add_edge(RESEARCH_WRITE_RESEARCH_BRIEF, RESEARCH_SUPERVISOR)

# Conditional routing after supervisor: research mode -> report, librarian mode -> navigation guide
deep_researcher_builder.add_conditional_edges(
    RESEARCH_SUPERVISOR,
    route_after_supervisor,
    {
        RESEARCH_FINAL_REPORT_GENERATION: RESEARCH_FINAL_REPORT_GENERATION,
        NAVIGATION_GUIDE_GENERATION: NAVIGATION_GUIDE_GENERATION,
    },
)

# Both output nodes lead to cleanup
deep_researcher_builder.add_edge(RESEARCH_FINAL_REPORT_GENERATION, CLEANUP_NODE)
deep_researcher_builder.add_edge(NAVIGATION_GUIDE_GENERATION, CLEANUP_NODE)
deep_researcher_builder.add_edge(QUICK_AGENT_NODE, CLEANUP_NODE)
deep_researcher_builder.add_edge(CLEANUP_NODE, END)


_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
deep_researcher = deep_researcher_builder.compile(
    debug=get_debug_mode(),
    name="deep_researcher_main_graph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
