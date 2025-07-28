from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from src.config.node_names import RESEARCH_TEAM, SUPERVISOR_NODE, SUPERVISOR_TOOLS_NODE
from src.config.settings import Configuration
from src.core.agents.research.researcher import researcher_subgraph
from src.core.agents.supervisor.supervisor_tools import supervisor_tools
from src.core.agents.tools.misc_utils import get_api_key_for_model
from src.schemas.state import ConductResearch, ResearchComplete, SupervisorState


async def supervisor(state: SupervisorState, config: RunnableConfig) -> dict:
    configurable = Configuration.from_runnable_config(config)
    supervisor_model_config = {"model": configurable.supervisor_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.supervisor_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.supervisor_model).bind(**supervisor_model_config)
    lead_researcher_tools = [ConductResearch, ResearchComplete]
    supervisor_model = configurable_model.bind_tools(lead_researcher_tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(supervisor_model_config)
    supervisor_messages = state.get("supervisor_messages", [])
    response = await supervisor_model.ainvoke(supervisor_messages)
    return {"supervisor_messages": [response], "research_iterations": state.get("research_iterations", 0) + 1}


supervisor_builder = StateGraph(state_schema=SupervisorState, config_schema=Configuration)

# Add nodes with comprehensive operational xmetadata
supervisor_builder.add_node(
    node=SUPERVISOR_TOOLS_NODE,
    action=supervisor_tools,
    destinations=[SUPERVISOR_NODE, END, RESEARCH_TEAM],
    metadata={
        "description": "Processes supervisor tool calls and routes to appropriate actions",
        "type": "routing_node",
        "interaction": "internal",
        "criticality": "critical",
        "command_based_routing": True,
        "tool_execution": True,
        "expected_duration": "short",
        "routing_targets": ["supervisor", "end", "research_team"],
        "dependencies": ["supervisor_messages", "tool_calls"],
        "outputs": ["routing_command", "tool_results"],
    },
)

supervisor_builder.add_node(
    node=SUPERVISOR_NODE,
    action=supervisor,
    metadata={
        "description": "Main supervisor decision-making node for research coordination",
        "type": "decision_node",
        "interaction": "internal",
        "criticality": "critical",
        "llm_powered": True,
        "tool_calling": True,
        "expected_duration": "medium",
        "dependencies": ["research_brief", "previous_results"],
        "outputs": ["supervisor_messages", "research_decisions"],
    },
)

supervisor_builder.add_node(
    node=RESEARCH_TEAM,
    action=researcher_subgraph,
    metadata={
        "description": "Parallel research team execution subgraph",
        "type": "worker_subgraph",
        "interaction": "internal",
        "criticality": "high",
        "parallel_capable": True,
        "send_api_target": True,
        "concurrent_execution": True,
        "expected_duration": "long",
        "dependencies": ["research_topics"],
        "outputs": ["research_results", "completed_research"],
    },
)

supervisor_builder.add_edge(START, SUPERVISOR_NODE)
supervisor_builder.add_edge(SUPERVISOR_NODE, SUPERVISOR_TOOLS_NODE)
supervisor_builder.add_edge(RESEARCH_TEAM, SUPERVISOR_TOOLS_NODE)

supervisor_subgraph = supervisor_builder.compile(
    debug=True,
    name="supervisor_coordination_graph",
    interrupt_before=None,
    interrupt_after=None,
)
