"""Generate Navigation Guide - Final output for librarian mode.

This module creates the final navigation guide output for users,
equivalent to final_report_generation.py but for navigation mode.
Instead of synthesizing answers, it produces a structured resource guide.
"""

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig

from src.config.settings import Configuration
from src.core.agents.tools.misc_utils import get_today_str
from src.core.agents.tools.token_utils import get_model_token_limit, is_token_limit_exceeded
from src.schemas.state import AgentState
from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, EVENT_FINAL_RESPONSE, emit_custom_event
from src.utils.model_factory import init_model


async def generate_navigation_guide(state: AgentState, config: RunnableConfig):
    """Generate the final navigation guide for librarian mode.

    This is the librarian-mode equivalent of final_report_generation.
    Instead of synthesizing a comprehensive answer, it creates a structured
    navigation guide with resource cards and exploration paths.

    Args:
        state: The agent state containing navigation findings
        config: Runnable configuration

    Returns:
        Updated state with final navigation guide in messages
    """
    cleared_state = {
        "notes": {"type": "override", "value": []},
        "supervisor_messages": {"type": "override", "value": []},
        "raw_notes": {"type": "override", "value": []},
    }

    configurable = Configuration.from_runnable_config(config)
    llm = init_model(configurable.final_report_model, temperature=0)

    # Get navigation findings (equivalent to research notes)
    findings = state.get("notes", [])

    current_retry = 0
    max_retries = 5
    findings_token_limit = 0

    while current_retry <= max_retries:
        # Use navigation_guide_prompt instead of final_report_generation_prompt
        navigation_guide_prompt = configurable.navigation_guide_prompt.format(
            research_brief=state.get("research_brief", ""),
            messages=get_buffer_string(state.get("messages", [])),
            findings=findings,
            date=get_today_str(),
        )

        try:
            emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Creating resource navigation guide..."})

            emit_custom_event(EVENT_FINAL_RESPONSE, {"is_final": True})

            # Generate navigation guide
            navigation_guide = await llm.ainvoke([HumanMessage(content=navigation_guide_prompt)], config)

            # Add metadata to indicate this is a navigation response
            navigation_guide.additional_kwargs = {
                "final_documents": state.get("final_documents", []),
                "supervisor_messages": state.get("supervisor_messages", []),
                "is_final_response": True,
                "response_type": "navigation_guide",  # Mark as navigation output
                "librarian_mode": True,
            }

            emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Navigation Guide Complete"})

            return {
                "final_report": navigation_guide.content,
                "messages": [navigation_guide],
                **cleared_state,
            }

        except Exception as e:
            if is_token_limit_exceeded(e, configurable.final_report_model):
                if current_retry == 0:
                    model_token_limit = get_model_token_limit(configurable.final_report_model)
                    if not model_token_limit:
                        return {
                            "final_report": (f"Error generating navigation guide: Token limit exceeded. " f"Could not determine model's maximum context length. " f"Please update the model map. Error: {e}"),
                            **cleared_state,
                        }
                    findings_token_limit = model_token_limit * 4
                else:
                    findings_token_limit = int(findings_token_limit * 0.9)

                print(f"Reducing navigation findings to {findings_token_limit} chars")
                findings = findings[:findings_token_limit]
                current_retry += 1
            else:
                return {
                    "final_report": f"Error generating navigation guide: {e}",
                    **cleared_state,
                    "messages": [AIMessage(content=f"Error generating navigation guide: {e}")],
                }

    return {
        "final_report": "Error generating navigation guide: Maximum retries exceeded",
        "messages": [AIMessage(content="Error: Maximum retries exceeded generating navigation guide")],
        **cleared_state,
    }


async def final_output_router(state: AgentState, config: RunnableConfig):
    """Route to appropriate final output generation based on mode.

    This function determines whether to use:
    - generate_navigation_guide (librarian mode)
    - final_report_generation (research mode)

    Args:
        state: Agent state
        config: Runnable configuration

    Returns:
        Result from the appropriate output generator
    """
    configurable = Configuration.from_runnable_config(config)

    if configurable.librarian_mode:
        return await generate_navigation_guide(state, config)
    else:
        # Import here to avoid circular imports
        from src.core.agents.generation.final_report_generation import final_report_generation

        return await final_report_generation(state, config)
