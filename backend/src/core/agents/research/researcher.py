import os as _os

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.config.node_names import (
    QUERY_TRANSFORMER_NODE,
    RESEARCH_COMPRESS_RESEARCH,
    RESEARCH_PACKAGE_OUTPUT,
    RESEARCH_RESEARCHER,
    RESEARCH_RESEARCHER_TOOLS,
)
from src.config.settings import Configuration
from src.core.agents.query_translation.query_transformer import query_transformer
from src.core.agents.research.compress_research import compress_research
from src.core.agents.research.researcher_tools import researcher_tools
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str, safe_get
from src.schemas.state import ResearcherOutputState, ResearcherSendOutputState, ResearcherState
from src.utils.debug import get_debug_mode
from src.utils.model_factory import init_model


def _has_pending_tool_calls(messages: list) -> bool:
    """Return True if there's an assistant message with tool_calls
    that is not followed by corresponding ToolMessage replies.

    Strategy: find the last assistant message that includes tool_calls.
    Verify that all its tool_call ids appear in subsequent ToolMessages
    before any non-tool message. If any are missing, tool calls are pending.
    """
    if not messages:
        return False

    # Find the last assistant message with tool_calls
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

    # Collect tool_call_ids that must be answered
    expected_ids = {call.get("id") for call in last_ai_tool_calls if isinstance(call, dict)}
    if not expected_ids:
        return False

    # Walk forward from that assistant message and collect ToolMessage ids
    observed_ids = set()
    for j in range(last_ai_idx + 1, len(messages)):
        m = messages[j]
        # Stop once we hit any non-tool message; tool replies must be contiguous
        if not isinstance(m, ToolMessage) and safe_get(m, "type") != "tool":
            break
        tool_call_id = safe_get(m, "tool_call_id")
        if tool_call_id:
            observed_ids.add(tool_call_id)

    # If any expected tool_call id is missing, tool calls are pending
    return not expected_ids.issubset(observed_ids)





async def researcher(state: ResearcherState, config: RunnableConfig) -> dict:
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    # Hard cap: if we've reached the max tool-call iterations, avoid new LLM calls.
    if state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls:
        # If there are pending tool calls, route to tools so they can answer or short-circuit them.
        if _has_pending_tool_calls(researcher_messages):
            return Command(goto=RESEARCH_RESEARCHER_TOOLS)
        # Otherwise, proceed to compress with what we have.
        return Command(goto=RESEARCH_COMPRESS_RESEARCH)
    # If there are any pending tool calls in history, route to tool executor
    if _has_pending_tool_calls(researcher_messages):
        return Command(goto=RESEARCH_RESEARCHER_TOOLS)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found to conduct research: Please configure either your search API or add MCP tools to your configuration.")
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config)}
    llm = init_model(configurable.research_model, disable_streaming=configurable.disable_streaming).bind(**research_model_config)
    researcher_system_prompt = configurable.research_system_prompt.format(mcp_prompt=configurable.mcp_prompt or "", date=get_today_str())
    research_model = llm.bind_tools(tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    # Place system prompt first to avoid breaking tool_call reply sequencing
    response = await research_model.ainvoke([SystemMessage(content=researcher_system_prompt)] + researcher_messages)
    return {"researcher_messages": [response], "tool_call_iterations": state.get("tool_call_iterations", 0) + 1}


def package_output(state: ResearcherState) -> ResearcherSendOutputState:
    """Package the researcher's final results for supervisor aggregation.

    Wraps the ResearcherOutputState into a list under
    `completed_research_results` so the supervisor can match results back to
    ConductResearch tool calls.
    """
    # Documents are now aggregated in state by researcher_tools
    docs = state.get("documents", [])
    return {
        "completed_research_results": [
            ResearcherOutputState(
                compressed_research=state.get("compressed_research", ""),
                raw_notes=state.get("raw_notes", []),
                documents=docs,
            )
        ]
    }


researcher_builder = StateGraph(state_schema=ResearcherState, output_schema=ResearcherSendOutputState, context_schema=Configuration)

researcher_builder.add_node(
    node=RESEARCH_RESEARCHER,
    action=researcher,
    metadata={
        "description": "Main researcher agent that conducts research using available tools",
        "type": "agent_node",
        "interaction": "tool_calling",
        "criticality": "high",
        "llm_powered": True,
        "tool_binding": True,
        "expected_duration": "medium",
        "max_iterations": "configurable",
        "dependencies": ["research_topic", "available_tools"],
        "outputs": ["researcher_messages", "tool_calls"],
    },
)

researcher_builder.add_node(
    node=RESEARCH_RESEARCHER_TOOLS,
    destinations=[RESEARCH_RESEARCHER, END, QUERY_TRANSFORMER_NODE, RESEARCH_COMPRESS_RESEARCH],
    action=researcher_tools,
    metadata={
        "description": "Executes research tools and processes tool call results",
        "type": "tool_execution_node",
        "interaction": "external_apis",
        "criticality": "high",
        "command_based_routing": True,
        "async_execution": True,
        "expected_duration": "variable",
        "tool_types": ["search", "web_scraping", "document_retrieval"],
        "dependencies": ["tool_calls", "research_context"],
        "outputs": ["tool_results", "processed_data", "routing_decision"],
    },
)

researcher_builder.add_node(
    node=RESEARCH_COMPRESS_RESEARCH,
    action=compress_research,
    metadata={
        "description": "Compresses and summarizes research findings for output",
        "type": "processing_node",
        "interaction": "internal",
        "criticality": "medium",
        "llm_powered": True,
        "summarization": True,
        "expected_duration": "short",
        "dependencies": ["tool_results", "research_data"],
        "outputs": ["compressed_results", "research_summary"],
    },
)

researcher_builder.add_node(
    node=RESEARCH_PACKAGE_OUTPUT,
    action=package_output,
    metadata={
        "description": "Packages research output for supervisor aggregation",
        "type": "output_packaging_node",
        "interaction": "internal",
        "criticality": "medium",
        "expected_duration": "short",
        "dependencies": ["compressed_research", "raw_notes"],
        "outputs": ["completed_research_results"],
    },
)

researcher_builder.add_node(
    node=QUERY_TRANSFORMER_NODE,
    action=query_transformer,
    metadata={
        "description": "Transforms and optimizes research queries using multiple strategies",
        "type": "query_processing_node",
        "interaction": "internal_routing",
        "criticality": "high",
        "llm_powered": True,
        "strategy_selection": True,
        "expected_duration": "medium",
        "query_strategies": ["contextual", "decomposition", "hyde", "factual", "multi_query", "step_back"],
        "dependencies": ["research_query", "context"],
        "outputs": ["transformed_context", "optimized_query"],
    },
)

# Graph flow with conditional routing
researcher_builder.add_edge(START, RESEARCH_RESEARCHER)
researcher_builder.add_edge(RESEARCH_RESEARCHER, RESEARCH_RESEARCHER_TOOLS)
researcher_builder.add_edge(QUERY_TRANSFORMER_NODE, RESEARCH_RESEARCHER_TOOLS)
researcher_builder.add_edge(RESEARCH_COMPRESS_RESEARCH, RESEARCH_PACKAGE_OUTPUT)
researcher_builder.add_edge(RESEARCH_PACKAGE_OUTPUT, END)


_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
researcher_subgraph = researcher_builder.compile(
    debug=get_debug_mode(),
    name="researcher_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
