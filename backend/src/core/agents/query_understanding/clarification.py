import uuid
from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.config.node_names import RESEARCH_CLARIFY_WITH_USER, RESEARCH_WRITE_RESEARCH_BRIEF
from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.schemas.state import AgentState
from src.utils.model_factory import init_model
from src.utils.events import emit_final_response_signal


class StartResearch(BaseModel):
    """Call this tool when you have sufficient information to start the research."""
    verification: str = Field(
        description="A brief acknowledgement message that you will now start research based on the provided information.",
    )


async def clarify_with_user(state: AgentState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        return Command(goto=RESEARCH_WRITE_RESEARCH_BRIEF)
    
    messages = state.get("summarized_messages", state["messages"])
    
    llm = init_model(
        configurable.clarify_with_user_model, 
        disable_streaming=configurable.disable_streaming, 
        node_name=RESEARCH_CLARIFY_WITH_USER
    )
    
    model = llm.bind_tools([StartResearch])
    
    emit_final_response_signal(True)

    response = await model.ainvoke(
        [
            HumanMessage(
                content=configurable.clarify_with_user_prompt.format(
                    messages=get_buffer_string(messages),
                    date=get_today_str(),
                )
            )
        ],
        config
    )
    
    if response.tool_calls:
        emit_final_response_signal(False)
        
        tool_call = response.tool_calls[0]
        verification_message = tool_call["args"].get("verification", "Starting research...")
        
        return Command(
            goto=RESEARCH_WRITE_RESEARCH_BRIEF, 
            update={
                "messages": [AIMessage(content=verification_message)]
            }
        )
    
    response.additional_kwargs["is_final_response"] = True
    
    return Command(
        goto=END, 
        update={
            "messages": [response]
        }
    )
