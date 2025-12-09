from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.schemas.state import AgentState
from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event
from src.utils.model_factory import init_model


class ResearchQuestion(BaseModel):
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )
    urls: list[str] = Field(
        default=[],
        description="List of URLs provided by the user in the conversation that should be researched.",
    )


async def write_research_brief(state: AgentState, config: RunnableConfig) -> dict:
    configurable = Configuration.from_runnable_config(config)

    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Formulating research strategy..."})

    write_model_config = {"model": configurable.transform_messages_into_research_topic_model, "max_tokens": configurable.research_model_max_tokens, "api_key": get_api_key_for_model(configurable.transform_messages_into_research_topic_model, config)}
    llm = init_model(configurable.transform_messages_into_research_topic_model, disable_streaming=configurable.disable_streaming).bind(**write_model_config)
    write_brief_model = llm.with_structured_output(ResearchQuestion).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(write_model_config)
    source_messages = state.get("summarized_messages", state.get("messages", []))
    response = await write_brief_model.ainvoke(
        [
            HumanMessage(
                content=configurable.transform_messages_into_research_topic_prompt.format(
                    messages=get_buffer_string(source_messages),
                    date=get_today_str(),
                )
            )
        ]
    )

    supervisor_content = [SystemMessage(content=configurable.lead_supervisor_prompt.format(date=get_today_str(), max_concurrent_research_units=configurable.max_concurrent_research_units)), HumanMessage(content=response.research_brief)]

    if response.urls:
        url_list = "\n".join(response.urls)
        supervisor_content.append(SystemMessage(content=f"User provided the following URLs to research:\n{url_list}"))

    return {
        "research_brief": response.research_brief,
        "supervisor_messages": {"type": "override", "value": supervisor_content},
    }
