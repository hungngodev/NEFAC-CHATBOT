import asyncio
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from backend.src.core.agents.tools.main import get_notes_from_tool_calls, get_today_str, is_token_limit_exceeded
from src.config.node_names import SUPERVISOR_NODE
from src.config.settings import Configuration
from src.core.agents.research.researcher import researcher_subgraph
from src.schemas.state import SupervisorState


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]
    # Exit Criteria
    # 1. We have exceeded our max guardrail research iterations
    # 2. No tool calls were made by the supervisor
    # 3. The most recent message contains a ResearchComplete tool call and there is only one tool call in the message
    exceeded_allowed_iterations = research_iterations >= configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls)
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})
    # Otherwise, conduct research and gather results.
    try:
        all_conduct_research_calls = [tool_call for tool_call in most_recent_message.tool_calls if tool_call["name"] == "ConductResearch"]
        conduct_research_calls = all_conduct_research_calls[: configurable.max_concurrent_research_units]
        overflow_conduct_research_calls = all_conduct_research_calls[configurable.max_concurrent_research_units :]
        researcher_system_prompt = configurable.research_system_prompt.format(mcp_prompt=configurable.mcp_prompt or "", date=get_today_str())
        coros = [researcher_subgraph.ainvoke({"researcher_messages": [SystemMessage(content=researcher_system_prompt), HumanMessage(content=tool_call["args"]["research_topic"])], "research_topic": tool_call["args"]["research_topic"]}, config) for tool_call in conduct_research_calls]
        tool_results = await asyncio.gather(*coros)
        tool_messages = [ToolMessage(content=observation.get("compressed_research", "Error synthesizing research report: Maximum retries exceeded"), name=tool_call["name"], tool_call_id=tool_call["id"]) for observation, tool_call in zip(tool_results, conduct_research_calls)]
        # Handle any tool calls made > max_concurrent_research_units
        for overflow_conduct_research_call in overflow_conduct_research_calls:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {configurable.max_concurrent_research_units} or fewer research units.",
                    name="ConductResearch",
                    tool_call_id=overflow_conduct_research_call["id"],
                )
            )
        raw_notes_concat = "\n".join(["\n".join(observation.get("raw_notes", [])) for observation in tool_results])
        return Command(goto=SUPERVISOR_NODE, update={"supervisor_messages": tool_messages, "raw_notes": [raw_notes_concat]})
    except Exception as e:
        if is_token_limit_exceeded(e, configurable.research_model):
            print(f"Token limit exceeded while reflecting: {e}")
        else:
            print(f"Other error in reflection phase: {e}")
        return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})
