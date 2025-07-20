from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from backend.src.core.agents.tools.main import get_all_tools, get_api_key_for_model
from src.config.node_names import RESEARCH_COMPRESS_RESEARCH, RESEARCH_RESEARCHER, RESEARCH_RESEARCHER_TOOLS
from src.config.settings import Configuration
from src.core.agents.research.compress_research import compress_research
from src.core.agents.research.researcher_tools import researcher_tools
from src.schemas.state import ResearcherOutputState, ResearcherState


async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher_tools"]]:
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found to conduct research: Please configure either your search API or add MCP tools to your configuration.")
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**research_model_config)
    research_model = configurable_model.bind_tools(tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    # NOTE: Need to add fault tolerance here.
    response = await research_model.ainvoke(researcher_messages)
    return Command(goto=RESEARCH_RESEARCHER_TOOLS, update={"researcher_messages": [response], "tool_call_iterations": state.get("tool_call_iterations", 0) + 1})


researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState, config_schema=Configuration)
researcher_builder.add_node(RESEARCH_RESEARCHER, researcher)
researcher_builder.add_node(RESEARCH_RESEARCHER_TOOLS, researcher_tools)
researcher_builder.add_node(RESEARCH_COMPRESS_RESEARCH, compress_research)
researcher_builder.add_edge(START, RESEARCH_RESEARCHER)
researcher_builder.add_edge(RESEARCH_COMPRESS_RESEARCH, END)
researcher_subgraph = researcher_builder.compile()
