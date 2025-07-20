import asyncio
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from backend.src.core.agents.tools.main import anthropic_websearch_called, get_all_tools, openai_websearch_called
from src.config.settings import Configuration
from src.schemas.state import ResearcherState


async def execute_tool_safely(tool, args, config):
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher", "compress_research"]]:
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]
    # Early Exit Criteria: No tool calls (or native web search calls)were made by the researcher
    if not most_recent_message.tool_calls and not (openai_websearch_called(most_recent_message) or anthropic_websearch_called(most_recent_message)):
        return Command(
            goto="compress_research",
        )
    # Otherwise, execute tools and gather results.
    tools = await get_all_tools(config)
    tools_by_name = {tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool for tool in tools}
    tool_calls = most_recent_message.tool_calls
    coros = [execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) for tool_call in tool_calls]
    observations = await asyncio.gather(*coros)
    tool_outputs = [ToolMessage(content=observation, name=tool_call["name"], tool_call_id=tool_call["id"]) for observation, tool_call in zip(observations, tool_calls)]

    # Late Exit Criteria: We have exceeded our max guardrail tool call iterations or the most recent message contains a ResearchComplete tool call
    # These are late exit criteria because we need to add ToolMessages
    if state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls or any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls):
        return Command(
            goto="compress_research",
            update={
                "researcher_messages": tool_outputs,
            },
        )
    return Command(
        goto="researcher",
        update={
            "researcher_messages": tool_outputs,
        },
    )
