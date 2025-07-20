import asyncio
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from backend.src.core.agents.tools.main import get_api_key_for_model, get_notes_from_tool_calls, get_today_str, is_token_limit_exceeded
from src.config.prompts import RESEARCH_SYSTEM_PROMPT
from src.config.settings import Configuration
from src.core.agents.query_understanding.clarification import clarify_with_user
from src.core.agents.research.compress_research import compress_research
from src.core.agents.research.final_report_generation import final_report_generation
from src.core.agents.research.researcher import researcher
from src.core.agents.research.researcher_tools import researcher_tools
from src.core.agents.research.write_research_brief import write_research_brief
from src.schemas.state import AgentInputState, AgentState, ConductResearch, ResearchComplete, ResearcherOutputState, ResearcherState, SupervisorState

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**research_model_config)
    lead_researcher_tools = [ConductResearch, ResearchComplete]
    research_model = configurable_model.bind_tools(lead_researcher_tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)
    return Command(goto="supervisor_tools", update={"supervisor_messages": [response], "research_iterations": state.get("research_iterations", 0) + 1})


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
        researcher_system_prompt = RESEARCH_SYSTEM_PROMPT.format(mcp_prompt=configurable.mcp_prompt or "", date=get_today_str())
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
        return Command(goto="supervisor", update={"supervisor_messages": tool_messages, "raw_notes": [raw_notes_concat]})
    except Exception as e:
        if is_token_limit_exceeded(e, configurable.research_model):
            print(f"Token limit exceeded while reflecting: {e}")
        else:
            print(f"Other error in reflection phase: {e}")
        return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})


supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_subgraph = supervisor_builder.compile()


researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState, config_schema=Configuration)
researcher_builder.add_node("researcher", researcher)
researcher_builder.add_node("researcher_tools", researcher_tools)
researcher_builder.add_node("compress_research", compress_research)
researcher_builder.add_edge(START, "researcher")
researcher_builder.add_edge("compress_research", END)
researcher_subgraph = researcher_builder.compile()


deep_researcher_builder = StateGraph(AgentState, input=AgentInputState, config_schema=Configuration)
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)
deep_researcher_builder.add_node("final_report_generation", final_report_generation)
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("research_supervisor", "final_report_generation")
deep_researcher_builder.add_edge("final_report_generation", END)

deep_researcher = deep_researcher_builder.compile()
