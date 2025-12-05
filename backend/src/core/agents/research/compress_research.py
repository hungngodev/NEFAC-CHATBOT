from langchain_core.messages import HumanMessage, SystemMessage, filter_messages
from langchain_core.runnables import RunnableConfig

from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.core.agents.tools.token_utils import is_token_limit_exceeded
from src.schemas.state import ResearcherState
from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event
from src.utils.model_factory import init_model


async def compress_research(state: ResearcherState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)

    # Emit progress update
    research_loop = state.get("research_iterations", 0)
    max_iter = getattr(configurable, "max_researcher_iterations", 3)
    current_loop = max(1, research_loop)

    # End of loop progress: 10% + (Loop / MaxLoops) * 80%
    progress = min(90, 10 + ((current_loop / max_iter) * 80))

    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": f"Summarizing findings (Loop {current_loop})...", "progress": progress, "total_steps": 100, "estimated_time_remaining": max(30, 600 - (current_loop * 150))})

    synthesis_attempts = 0
    llm = init_model(configurable.compress_research_model, disable_streaming=configurable.disable_streaming)
    synthesizer_model = llm.with_config({"model": configurable.compress_research_model, "max_tokens": configurable.compression_model_max_tokens, "api_key": get_api_key_for_model(configurable.compress_research_model, config)})
    researcher_messages = state.get("researcher_messages", [])
    # Update the system prompt to now focus on compression rather than research.
    researcher_messages[0] = SystemMessage(content=configurable.compress_research_system_prompt.format(date=get_today_str()))
    researcher_messages.append(HumanMessage(content=configurable.compress_research_simple_human_message))
    while synthesis_attempts < 3:
        try:
            response = await synthesizer_model.ainvoke(researcher_messages)
            return {
                "compressed_research": str(response.content),
                "raw_notes": ["\n".join([str(m.content) for m in filter_messages(researcher_messages, include_types=["tool", "ai"])])],
            }
        except Exception as e:
            synthesis_attempts += 1
            if is_token_limit_exceeded(e, configurable.compress_research_model):
                print(f"Token limit exceeded while synthesizing: {e}. Pruning the messages to try again.")
                continue
            print(f"Error synthesizing research report: {e}")
    return {"compressed_research": "Error synthesizing research report: Maximum retries exceeded", "raw_notes": ["\n".join([str(m.content) for m in filter_messages(researcher_messages, include_types=["tool", "ai"])])]}
