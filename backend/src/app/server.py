import os as _os

from langgraph.graph import END, START, StateGraph

from src.config.node_names import MEMORY_SUMMARIZER_NODE, RESEARCH_CLARIFY_WITH_USER, RESEARCH_FINAL_REPORT_GENERATION, RESEARCH_SUPERVISOR, RESEARCH_WRITE_RESEARCH_BRIEF
from src.config.settings import Configuration
from src.core.agents.generation.final_report_generation import final_report_generation
from src.core.agents.memory.summarizer import summarizer
from src.core.agents.query_understanding.clarification import clarify_with_user
from src.core.agents.query_understanding.write_research_brief import write_research_brief
from src.core.agents.supervisor.supervisor import supervisor_subgraph
from src.schemas.state import AgentInputState, AgentState

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

deep_researcher_builder.add_edge(START, MEMORY_SUMMARIZER_NODE)
deep_researcher_builder.add_edge(MEMORY_SUMMARIZER_NODE, RESEARCH_CLARIFY_WITH_USER)
deep_researcher_builder.add_edge(RESEARCH_WRITE_RESEARCH_BRIEF, RESEARCH_SUPERVISOR)
deep_researcher_builder.add_edge(RESEARCH_SUPERVISOR, RESEARCH_FINAL_REPORT_GENERATION)
deep_researcher_builder.add_edge(RESEARCH_FINAL_REPORT_GENERATION, END)

_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
deep_researcher = deep_researcher_builder.compile(
    debug=True,
    name="deep_researcher_main_graph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
