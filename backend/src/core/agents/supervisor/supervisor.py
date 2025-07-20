from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph
from langgraph.types import Command

from backend.src.core.agents.tools.main import get_api_key_for_model
from src.config.node_names import SUPERVISOR_NODE, SUPERVISOR_TOOLS_NODE
from src.config.settings import Configuration
from src.core.agents.supervisor.supervisor_tools import supervisor_tools
from src.schemas.state import ConductResearch, ResearchComplete, SupervisorState


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**research_model_config)
    lead_researcher_tools = [ConductResearch, ResearchComplete]
    research_model = configurable_model.bind_tools(lead_researcher_tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)
    return Command(goto=SUPERVISOR_TOOLS_NODE, update={"supervisor_messages": [response], "research_iterations": state.get("research_iterations", 0) + 1})


supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
supervisor_builder.add_node(SUPERVISOR_NODE, supervisor)
supervisor_builder.add_node(SUPERVISOR_TOOLS_NODE, supervisor_tools)
supervisor_builder.add_edge(START, SUPERVISOR_NODE)
supervisor_subgraph = supervisor_builder.compile()
