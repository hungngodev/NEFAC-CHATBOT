from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.config.node_names import RESEARCH_SUPERVISOR
from src.config.settings import Configuration
from src.core.agents.tools.main import get_api_key_for_model, get_today_str
from src.schemas.state import AgentState


class ResearchQuestion(BaseModel):
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )


async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command[Literal["research_supervisor"]]:
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**research_model_config)
    research_model = configurable_model.with_structured_output(ResearchQuestion).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(research_model_config)
    response = await research_model.ainvoke([HumanMessage(content=configurable.transform_messages_into_research_topic_prompt.format(messages=get_buffer_string(state.get("messages", [])), date=get_today_str()))])
    return Command(
        goto=RESEARCH_SUPERVISOR,
        update={
            "research_brief": response.research_brief,
            "supervisor_messages": {"type": "override", "value": [SystemMessage(content=configurable.lead_researcher_prompt.format(date=get_today_str(), max_concurrent_research_units=configurable.max_concurrent_research_units)), HumanMessage(content=response.research_brief)]},
        },
    )
