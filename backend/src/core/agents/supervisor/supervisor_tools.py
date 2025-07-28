from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command, Send

from src.config.node_names import RESEARCH_TEAM, SUPERVISOR_NODE
from src.config.settings import Configuration
from src.core.agents.tools.main import get_notes_from_tool_calls
from src.core.agents.tools.token_utils import is_token_limit_exceeded
from src.schemas.state import SupervisorState


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> SupervisorState:
    configurable = Configuration.from_runnable_config(config)

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    completed_research_results = state.get("completed_research_results", [])
    research_tool_calls = state.get("research_tool_calls", [])

    most_recent_message = supervisor_messages[-1]
    exceeded_allowed_iterations = research_iterations >= configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(tool_call["name"] == "ResearchComplete" for tool_call in most_recent_message.tool_calls)

    # Process completed research results
    if completed_research_results and research_tool_calls:
        tool_messages = []
        raw_notes_parts = []

        for research_result, tool_call in zip(completed_research_results, research_tool_calls):
            tool_messages.append(ToolMessage(content=research_result.compressed_research or "Error synthesizing research report: Maximum retries exceeded", name=tool_call["name"], tool_call_id=tool_call["id"]))

            if research_result.raw_notes:
                raw_notes_parts.extend(research_result.raw_notes)

        return Command(goto=SUPERVISOR_NODE, update={"supervisor_messages": tool_messages, "raw_notes": ["\n".join(raw_notes_parts)], "completed_research_results": [], "research_tool_calls": []})

    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})

    try:
        all_conduct_research_calls = [tool_call for tool_call in most_recent_message.tool_calls if tool_call["name"] == "ConductResearch"]

        max_units = configurable.max_concurrent_research_units
        conduct_research_calls = all_conduct_research_calls[:max_units]
        overflow_conduct_research_calls = all_conduct_research_calls[max_units:]

        research_sends = [Send(RESEARCH_TEAM, {"researcher_messages": [HumanMessage(content=tool_call["args"]["research_topic"])], "research_topic": tool_call["args"]["research_topic"]}) for tool_call in conduct_research_calls]

        # Handle overflow as error messages
        overflow_messages = [ToolMessage(content=f"Error: Exceeded max concurrent research units ({max_units}). Please try again with fewer units.", name="ConductResearch", tool_call_id=tool_call["id"]) for tool_call in overflow_conduct_research_calls]

        return Command(goto=research_sends, update={"supervisor_messages": supervisor_messages + overflow_messages, "research_tool_calls": conduct_research_calls})

    except Exception as e:
        if is_token_limit_exceeded(e, configurable.research_model):
            print(f"Token limit exceeded while reflecting: {e}")
        else:
            print(f"Other error in reflection phase: {e}")
    return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})
