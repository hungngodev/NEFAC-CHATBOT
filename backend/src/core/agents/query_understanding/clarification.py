from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.config.node_names import RESEARCH_WRITE_RESEARCH_BRIEF
from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.schemas.state import AgentState


class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


async def clarify_with_user(state: AgentState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        return Command(goto=RESEARCH_WRITE_RESEARCH_BRIEF)
    messages = state["messages"]
    model_config = {"model": configurable.research_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.research_model, config), "tags": ["langsmith:nostream"]}
    configurable_model = init_chat_model(configurable.research_model).bind(**model_config)
    model = configurable_model.with_structured_output(ClarifyWithUser).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(model_config)
    response = await model.ainvoke([HumanMessage(content=configurable.clarify_with_user_prompt.format(messages=get_buffer_string(messages), date=get_today_str()))])
    if response.need_clarification:
        return Command(goto=END, update={"messages": [AIMessage(content=response.question)]})
    else:
        return Command(goto=RESEARCH_WRITE_RESEARCH_BRIEF, update={"messages": [AIMessage(content=response.verification)]})
