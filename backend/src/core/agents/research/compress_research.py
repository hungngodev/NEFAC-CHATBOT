from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, filter_messages
from langchain_core.runnables import RunnableConfig

from src.config.settings import Configuration
from src.core.agents.tools.main import get_api_key_for_model, get_today_str, is_token_limit_exceeded, remove_up_to_last_ai_message
from src.schemas.state import ResearcherState


async def compress_research(state: ResearcherState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    synthesis_attempts = 0
    configurable_model = init_chat_model(configurable.compression_model)
    synthesizer_model = configurable_model.with_config({"model": configurable.compression_model, "max_tokens": configurable.compression_model_max_tokens, "api_key": get_api_key_for_model(configurable.compression_model, config), "tags": ["langsmith:nostream"]})
    researcher_messages = state.get("researcher_messages", [])
    # Update the system prompt to now focus on compression rather than research.
    researcher_messages[0] = SystemMessage(content=configurable.compress_research_system_prompt.format(date=get_today_str()))
    researcher_messages.append(HumanMessage(content=configurable.compress_research_simple_human_message))
    while synthesis_attempts < 3:
        try:
            response = await synthesizer_model.ainvoke(researcher_messages)
            return {"compressed_research": str(response.content), "raw_notes": ["\n".join([str(m.content) for m in filter_messages(researcher_messages, include_types=["tool", "ai"])])]}
        except Exception as e:
            synthesis_attempts += 1
            if is_token_limit_exceeded(e, configurable.research_model):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                print(f"Token limit exceeded while synthesizing: {e}. Pruning the messages to try again.")
                continue
            print(f"Error synthesizing research report: {e}")
    return {"compressed_research": "Error synthesizing research report: Maximum retries exceeded", "raw_notes": ["\n".join([str(m.content) for m in filter_messages(researcher_messages, include_types=["tool", "ai"])])]}
