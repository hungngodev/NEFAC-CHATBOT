import os as _os

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.config.node_names import RESEARCH_TEAM, SUPERVISOR_NODE, SUPERVISOR_TOOLS_NODE
from src.config.settings import Configuration
from src.core.agents.research.researcher import researcher_subgraph
from src.core.agents.research.utils import emit_research_status
from src.core.agents.supervisor.supervisor_tools import supervisor_tools
from src.core.agents.tools.misc_utils import get_api_key_for_model, safe_get
from src.schemas.state import ConductResearch, ResearchComplete, SupervisorState
from src.utils.debug import get_debug_mode
from src.utils.model_factory import init_model


def _has_pending_tool_calls(messages: list) -> bool:
    if not messages:
        return False
    last_ai_idx = None
    last_ai_tool_calls = None
    for idx in range(len(messages) - 1, -1, -1):
        msg = messages[idx]
        tc = safe_get(msg, "tool_calls")
        if tc:
            last_ai_idx = idx
            last_ai_tool_calls = tc
            break
    if last_ai_idx is None or not last_ai_tool_calls:
        return False
    expected_ids = {call.get("id") for call in last_ai_tool_calls if isinstance(call, dict)}
    if not expected_ids:
        return False
    observed_ids = set()
    for j in range(last_ai_idx + 1, len(messages)):
        m = messages[j]
        if not isinstance(m, ToolMessage) and safe_get(m, "type") != "tool":
            break
        tool_call_id = safe_get(m, "tool_call_id")
        if tool_call_id:
            observed_ids.add(tool_call_id)
    return not expected_ids.issubset(observed_ids)


async def supervisor(state: SupervisorState, config: RunnableConfig) -> dict:
    configurable = Configuration.from_runnable_config(config)

    iteration = state.get("research_iterations", 0)
    emit_research_status(status=f"Coordinating research team (Iteration {iteration + 1})...")

    supervisor_model_config = {"model": configurable.supervisor_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.supervisor_model, config)}
    llm = init_model(configurable.supervisor_model, disable_streaming=configurable.disable_streaming, node_name=SUPERVISOR_NODE).bind(**supervisor_model_config)
    lead_researcher_tools = [ConductResearch, ResearchComplete]
    supervisor_model = llm.bind_tools(lead_researcher_tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(supervisor_model_config)
    supervisor_messages = state.get("supervisor_messages", [])
    if _has_pending_tool_calls(supervisor_messages):
        return Command(goto=SUPERVISOR_TOOLS_NODE)
    response = await supervisor_model.ainvoke(supervisor_messages)
    return {
        "supervisor_messages": [response],
        "research_iterations": state.get("research_iterations", 0) + 1,
    }


supervisor_builder = StateGraph(state_schema=SupervisorState, input_schema=SupervisorState, output_schema=SupervisorState, context_schema=Configuration)

supervisor_builder.add_node(
    node=SUPERVISOR_TOOLS_NODE,
    destinations=[RESEARCH_TEAM, SUPERVISOR_NODE, END],
    action=supervisor_tools,
    metadata={
        "description": "Executes supervisor's tool calls (delegation or completion)",
        "type": "tool_execution_node",
        "interaction": "internal_routing",
        "criticality": "high",
        "command_based_routing": True,
        "expected_duration": "short",
        "dependencies": ["supervisor_messages"],
        "outputs": ["research_tool_calls", "completed_research_results"],
    },
)

supervisor_builder.add_node(
    node=SUPERVISOR_NODE,
    action=supervisor,
    metadata={
        "description": "Supervisor agent that plans and delegates research tasks",
        "type": "supervisor_node",
        "interaction": "planning",
        "criticality": "critical",
        "llm_powered": True,
        "expected_duration": "medium",
        "dependencies": ["research_brief", "research_results"],
        "outputs": ["supervisor_messages", "research_iterations"],
    },
)

supervisor_builder.add_node(
    node=RESEARCH_TEAM,
    action=researcher_subgraph,
    metadata={
        "description": "Research team subgraph that executes delegated research tasks",
        "type": "worker_subgraph",
        "interaction": "research",
        "criticality": "high",
        "parallel_capable": True,
        "expected_duration": "long",
        "dependencies": ["research_topic"],
        "outputs": ["completed_research_results"],
    },
)

supervisor_builder.add_edge(START, SUPERVISOR_NODE)
supervisor_builder.add_edge(SUPERVISOR_NODE, SUPERVISOR_TOOLS_NODE)
supervisor_builder.add_edge(RESEARCH_TEAM, SUPERVISOR_TOOLS_NODE)


_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
supervisor_subgraph = supervisor_builder.compile(
    debug=get_debug_mode(),
    name="supervisor_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
