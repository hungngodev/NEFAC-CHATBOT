from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig

from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_api_key_for_model, get_today_str
from src.core.agents.tools.token_utils import get_model_token_limit, is_token_limit_exceeded
from src.schemas.state import AgentState
from src.utils.model_factory import init_model


async def final_report_generation(state: AgentState, config: RunnableConfig):
    notes = state.get("notes", [])
    cleared_state = {
        "notes": {"type": "override", "value": []},
    }
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
    }
    llm = init_model(configurable.final_report_model, disable_streaming=configurable.disable_streaming).with_config(writer_model_config)
    findings = "\n".join(notes)
    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        final_report_prompt = configurable.final_report_generation_prompt.format(research_brief=state.get("research_brief", ""), messages=get_buffer_string(state.get("messages", [])), findings=findings, date=get_today_str())
        try:
            final_report = await llm.with_config(writer_model_config).ainvoke([HumanMessage(content=final_report_prompt)])
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
                return {"final_report": f"Error generating final report: {e}", **cleared_state, "message": [AIMessage(content=f"Error generating final report: {e}")]}
    return {"final_report": "Error generating final report: Maximum retries exceeded", "messages": [final_report], **cleared_state}
