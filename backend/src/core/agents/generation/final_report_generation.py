from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from backend.src.core.agents.tools.main import get_api_key_for_model, get_model_token_limit, get_today_str, is_token_limit_exceeded
from src.config.settings import Configuration
from src.schemas.state import AgentState


async def final_report_generation(state: AgentState, config: RunnableConfig):
    notes = state.get("notes", [])
    cleared_state = {
        "notes": {"type": "override", "value": []},
    }
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
    }
    configurable_model = init_chat_model(configurable.final_report_model).with_config(writer_model_config)
    findings = "\n".join(notes)
    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        final_report_prompt = configurable.final_report_generation_prompt.format(research_brief=state.get("research_brief", ""), findings=findings, date=get_today_str())
        try:
            final_report = await configurable_model.with_config(writer_model_config).ainvoke([HumanMessage(content=final_report_prompt)])
            return {"final_report": final_report.content, "messages": [final_report], **cleared_state}
        except Exception as e:
            if is_token_limit_exceeded(e, configurable.final_report_model):
                if current_retry == 0:
                    model_token_limit = get_model_token_limit(configurable.final_report_model)
                    if not model_token_limit:
                        return {"final_report": f"Error generating final report: Token limit exceeded, however, we could not determine the model's maximum context length. Please update the model map in deep_researcher/utils.py with this information. {e}", **cleared_state}
                    findings_token_limit = model_token_limit * 4
                else:
                    findings_token_limit = int(findings_token_limit * 0.9)
                print("Reducing the chars to", findings_token_limit)
                findings = findings[:findings_token_limit]
                current_retry += 1
            else:
                # If not a token limit exceeded error, then we just throw an error.
                return {"final_report": f"Error generating final report: {e}", **cleared_state}
    return {"final_report": "Error generating final report: Maximum retries exceeded", "messages": [final_report], **cleared_state}
