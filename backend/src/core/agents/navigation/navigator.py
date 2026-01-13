"""Navigator agent subgraph for librarian-style resource navigation.

This module provides a navigator agent that discovers resources and creates
navigation guides instead of synthesizing answers. It mirrors the researcher
subgraph structure but uses navigation tools and librarian prompts.
"""

import os as _os

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.config.node_names import (
    QUERY_TRANSFORMER_NODE,
)
from src.config.settings import Configuration
from src.core.agents.query_translation.query_transformer import query_transformer
from src.core.agents.tools.main import get_all_tools
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str, safe_get
from src.schemas.navigation_state import (
    NavigationOutput,
    NavigatorOutputState,
    NavigatorSendOutputState,
    NavigatorState,
)
from src.utils.debug import get_debug_mode
from src.utils.model_factory import init_model

# Navigator node names (parallel to researcher nodes)
NAVIGATOR_AGENT = "navigator"
NAVIGATOR_TOOLS = "navigator_tools"
NAVIGATOR_FORMAT_OUTPUT = "format_navigation"
NAVIGATOR_PACKAGE_OUTPUT = "package_navigation"


def _has_pending_tool_calls(messages: list) -> bool:
    """Return True if there's an assistant message with tool_calls
    that is not followed by corresponding ToolMessage replies.
    """
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


def emit_navigation_status(status: str) -> None:
    """Emit navigation status for debugging/monitoring."""
    # Simple print for now, can be replaced with proper event emission
    if _os.getenv("DEBUG", "").lower() == "true":
        print(f"[Navigator] {status}")


async def navigator(state: NavigatorState, config: RunnableConfig) -> dict:
    """Main navigator agent that discovers resources using navigation tools.

    This is the librarian-mode equivalent of the researcher agent. Instead of
    synthesizing answers, it navigates to relevant resources and creates
    structured resource cards.
    """
    configurable = Configuration.from_runnable_config(config)
    navigator_messages = state.get("navigator_messages", [])

    # Hard cap: if we've reached the max tool-call iterations, avoid new LLM calls.
    max_iterations = configurable.max_react_tool_calls
    if state.get("tool_call_iterations", 0) >= max_iterations:
        if _has_pending_tool_calls(navigator_messages):
            return Command(goto=NAVIGATOR_TOOLS)
        return Command(goto=NAVIGATOR_FORMAT_OUTPUT)

    # If there are any pending tool calls in history, route to tool executor
    if _has_pending_tool_calls(navigator_messages):
        return Command(goto=NAVIGATOR_TOOLS)

    # Get navigation tools (sitemap, metadata filter, section linker, etc.)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found for navigation: Please configure your navigation tools or MCP tools.")

    # Initialize the model with navigator system prompt
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }
    llm = init_model(configurable.research_model, disable_streaming=configurable.disable_streaming).bind(**research_model_config)

    # Use navigator system prompt (librarian mode)
    navigator_system_prompt = configurable.navigator_system_prompt.format(
        mcp_prompt=configurable.mcp_prompt or "",
        date=get_today_str(),
    )

    navigator_model = llm.bind_tools(tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)

    iteration = state.get("tool_call_iterations", 0)
    emit_navigation_status(f"Discovering resources (Step {iteration + 1})...")

    response = await navigator_model.ainvoke(
        [SystemMessage(content=navigator_system_prompt)] + navigator_messages,
        config,
    )

    return {
        "navigator_messages": [response],
        "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
    }


async def navigator_tools(state: NavigatorState, config: RunnableConfig) -> dict:
    """Execute navigation tools and route based on results.

    Similar to researcher_tools but handles navigation-specific tool outputs.
    """
    from langgraph.prebuilt import ToolNode

    # Config validation (result not used, just validating)
    navigator_messages = state.get("navigator_messages", [])

    if not navigator_messages:
        return Command(goto=NAVIGATOR_FORMAT_OUTPUT)

    last_message = navigator_messages[-1]
    tool_calls = safe_get(last_message, "tool_calls") or []

    if not tool_calls:
        return Command(goto=NAVIGATOR_FORMAT_OUTPUT)

    # Check for NavigationComplete signal
    for call in tool_calls:
        if isinstance(call, dict) and call.get("name") == "NavigationComplete":
            emit_navigation_status("Navigation complete signal received")
            # Create a placeholder response for NavigationComplete
            tool_msg = ToolMessage(
                content="Navigation complete. Formatting results.",
                tool_call_id=call.get("id", "unknown"),
            )
            return {
                "navigator_messages": [tool_msg],
                "update": Command(goto=NAVIGATOR_FORMAT_OUTPUT),
            }

    # Execute tools using ToolNode
    tools = await get_all_tools(config)
    tool_node = ToolNode(tools)

    try:
        tool_results = await tool_node.ainvoke({"messages": navigator_messages}, config)
        new_messages = tool_results.get("messages", [])

        # Extract notes from tool outputs for later formatting
        raw_notes = []
        for msg in new_messages:
            if isinstance(msg, ToolMessage):
                raw_notes.append(msg.content)

        emit_navigation_status(f"Processed {len(tool_calls)} tool calls")

        return {
            "navigator_messages": new_messages,
            "raw_notes": raw_notes,
        }

    except Exception as e:
        emit_navigation_status(f"Tool execution error: {e}")
        # Return error as tool message
        error_messages = []
        for call in tool_calls:
            if isinstance(call, dict):
                error_messages.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=call.get("id", "unknown"),
                    )
                )
        return {"navigator_messages": error_messages}


async def format_navigation(state: NavigatorState, config: RunnableConfig) -> dict:
    """Format the navigation findings into a clean NavigationOutput.

    This is the librarian-mode equivalent of compress_research. Instead of
    synthesizing answers, it formats discovered resources as ResourceCards.
    """
    configurable = Configuration.from_runnable_config(config)
    navigator_messages = state.get("navigator_messages", [])
    raw_notes = state.get("raw_notes", [])

    if not raw_notes:
        # Extract notes from messages if not already extracted
        raw_notes = []
        for msg in navigator_messages:
            if isinstance(msg, ToolMessage):
                raw_notes.append(msg.content)

    # Use format_navigation_prompt to create structured output
    format_prompt = configurable.format_navigation_prompt.format(date=get_today_str())

    # Build context from tool outputs
    findings_text = "\n\n---\n\n".join(raw_notes) if raw_notes else "No resources found."

    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }
    llm = init_model(
        configurable.research_model,
        disable_streaming=configurable.disable_streaming,
    ).bind(**research_model_config)

    full_prompt = f"{format_prompt}\n\n<Tool Outputs>\n{findings_text}\n</Tool Outputs>"

    emit_navigation_status("Formatting navigation results...")

    response = await llm.ainvoke([SystemMessage(content=full_prompt)], config)

    # Create NavigationOutput from the formatted response
    navigation_output = NavigationOutput(
        resources=[],  # Would be populated by structured output in production
        navigation_suggestions=[],
        hierarchy_context={},
        summary_note=response.content if hasattr(response, "content") else str(response),
        total_resources_found=len(raw_notes),
    )

    return {
        "navigation_output": navigation_output,
        "formatted_navigation": response.content if hasattr(response, "content") else str(response),
    }


def package_navigation_output(state: NavigatorState) -> NavigatorSendOutputState:
    """Package the navigator's final results for supervisor aggregation.

    Wraps the NavigatorOutputState into a list under `completed_navigation_results`
    so the supervisor can aggregate results from multiple navigators.
    """
    docs = state.get("documents", [])
    navigation_output = state.get("navigation_output")

    if navigation_output is None:
        navigation_output = NavigationOutput(
            resources=[],
            navigation_suggestions=[],
            hierarchy_context={},
            summary_note=str(state.get("formatted_navigation", "")),
            total_resources_found=0,
        )

    return {
        "completed_navigation_results": [
            NavigatorOutputState(
                navigation_output=navigation_output,
                raw_notes=state.get("raw_notes", []),
                documents=docs,
            )
        ]
    }


# After tool execution, route back to navigator for more tool calls or to formatting
def route_after_tools(state: NavigatorState) -> str:
    """Determine next step after tool execution."""
    navigator_messages = state.get("navigator_messages", [])

    # Check if the last message indicates completion
    if navigator_messages:
        last_msg = navigator_messages[-1]
        tool_calls = safe_get(last_msg, "tool_calls") or []
        for call in tool_calls:
            if isinstance(call, dict) and call.get("name") == "NavigationComplete":
                return NAVIGATOR_FORMAT_OUTPUT

    # Default: go back to navigator for more tool calls
    return NAVIGATOR_AGENT


# Build the navigator subgraph
navigator_builder = StateGraph(
    state_schema=NavigatorState,
    output_schema=NavigatorSendOutputState,
    context_schema=Configuration,
)

navigator_builder.add_node(
    node=NAVIGATOR_AGENT,
    action=navigator,
    metadata={
        "description": "Main navigator agent that discovers resources using navigation tools",
        "type": "agent_node",
        "interaction": "tool_calling",
        "criticality": "high",
        "llm_powered": True,
        "tool_binding": True,
        "mode": "librarian",
    },
)

navigator_builder.add_node(
    node=NAVIGATOR_TOOLS,
    action=navigator_tools,
    metadata={
        "description": "Executes navigation tools (sitemap, metadata filter, section linker)",
        "type": "tool_execution_node",
        "interaction": "external_apis",
        "criticality": "high",
        "mode": "librarian",
    },
)

navigator_builder.add_node(
    node=NAVIGATOR_FORMAT_OUTPUT,
    action=format_navigation,
    metadata={
        "description": "Formats navigation findings into ResourceCards",
        "type": "processing_node",
        "interaction": "internal",
        "llm_powered": True,
        "mode": "librarian",
    },
)

navigator_builder.add_node(
    node=NAVIGATOR_PACKAGE_OUTPUT,
    action=package_navigation_output,
    metadata={
        "description": "Packages navigation output for supervisor aggregation",
        "type": "output_packaging_node",
        "mode": "librarian",
    },
)

navigator_builder.add_node(
    node=QUERY_TRANSFORMER_NODE,
    action=query_transformer,
    metadata={
        "description": "Transforms and optimizes navigation queries",
        "type": "query_processing_node",
        "mode": "librarian",
    },
)

# Graph flow
navigator_builder.add_edge(START, NAVIGATOR_AGENT)
navigator_builder.add_edge(NAVIGATOR_AGENT, NAVIGATOR_TOOLS)
navigator_builder.add_edge(NAVIGATOR_TOOLS, NAVIGATOR_AGENT)  # Loop back for more tool calls
navigator_builder.add_edge(QUERY_TRANSFORMER_NODE, NAVIGATOR_TOOLS)
navigator_builder.add_edge(NAVIGATOR_FORMAT_OUTPUT, NAVIGATOR_PACKAGE_OUTPUT)
navigator_builder.add_edge(NAVIGATOR_PACKAGE_OUTPUT, END)

# Add conditional edge for completion detection
navigator_builder.add_conditional_edges(
    NAVIGATOR_TOOLS,
    route_after_tools,
    {
        NAVIGATOR_AGENT: NAVIGATOR_AGENT,
        NAVIGATOR_FORMAT_OUTPUT: NAVIGATOR_FORMAT_OUTPUT,
    },
)

_RL = int(_os.getenv("GRAPH_RECURSION_LIMIT", "60"))
navigator_subgraph = navigator_builder.compile(
    debug=get_debug_mode(),
    name="navigator_subgraph",
    interrupt_before=None,
    interrupt_after=None,
).with_config({"recursion_limit": _RL})
