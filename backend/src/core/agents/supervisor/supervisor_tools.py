from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command, Send

from src.config.node_names import RESEARCH_TEAM, SUPERVISOR_NODE
from src.config.settings import Configuration
from src.core.agents.tools.main import get_notes_from_tool_calls
from src.core.agents.tools.misc_utils import safe_get
from src.core.agents.tools.token_utils import is_token_limit_exceeded
from src.schemas.state import SupervisorState
from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> SupervisorState:
    configurable = Configuration.from_runnable_config(config)

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    completed_research_results = state.get("completed_research_results", [])
    research_tool_calls = state.get("research_tool_calls", [])

    # Safe accessors for tool_calls across message types/providers
    def _assistant_tool_calls(msg) -> list[dict]:
        calls = getattr(msg, "tool_calls", None)
        if calls:
            return calls
        ak = getattr(msg, "additional_kwargs", None) or {}
        return ak.get("tool_calls") or []

    most_recent_message = supervisor_messages[-1] if supervisor_messages else None
    exceeded_allowed_iterations = research_iterations >= configurable.max_researcher_iterations
    last_tool_calls = _assistant_tool_calls(most_recent_message) if most_recent_message else []
    no_tool_calls = len(last_tool_calls) == 0
    research_complete_tool_call = any((tc or {}).get("name") == "ResearchComplete" for tc in last_tool_calls)

    # Process completed research results
    if completed_research_results and research_tool_calls:
        tool_messages = []
        raw_notes_parts = []

        batch_docs = []

        for research_result, tool_call in zip(completed_research_results, research_tool_calls):
            # Extract fields once
            compressed = safe_get(research_result, "compressed_research")
            raw_notes_val = safe_get(research_result, "raw_notes")
            docs = safe_get(research_result, "documents", [])

            # Build ToolMessage content
            content_parts = [compressed or "Error synthesizing research report: Maximum retries exceeded"]

            if docs:
                content_parts.append(f"\n\n[System Notification]: Extracted {len(docs)} documents from research and added to final documents.")
                batch_docs.extend(docs)

            tool_messages.append(
                ToolMessage(
                    content="".join(content_parts),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

            if raw_notes_val:
                raw_notes_parts.extend(raw_notes_val)

        return Command(goto=SUPERVISOR_NODE, update={"supervisor_messages": tool_messages, "raw_notes": ["\n".join(raw_notes_parts)], "completed_research_results": [], "research_tool_calls": [], "final_documents": batch_docs})

    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": "Research completed. Generating final report..."})
        return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})

    try:
        all_conduct_research_calls = [tc for tc in last_tool_calls if (tc or {}).get("name") == "ConductResearch"]

        max_units = configurable.max_concurrent_research_units
        conduct_research_calls = all_conduct_research_calls[:max_units]
        overflow_conduct_research_calls = all_conduct_research_calls[max_units:]

        research_sends = []
        for tool_call in conduct_research_calls:
            topic = tool_call["args"]["research_topic"]
            emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, {"status": f"Starting research on: {topic}"})
            research_sends.append(Send(RESEARCH_TEAM, {"researcher_messages": [HumanMessage(content=topic)], "research_topic": topic, "research_iterations": research_iterations}))

        # Handle overflow as error messages
        overflow_messages = [ToolMessage(content=f"Error: Exceeded max concurrent research units ({max_units}). Please try again with fewer units.", name="ConductResearch", tool_call_id=tool_call["id"]) for tool_call in overflow_conduct_research_calls]

        # Only append the overflow messages (delta). Avoid re-adding the full history which caused duplication.
        return Command(goto=research_sends, update={"supervisor_messages": overflow_messages, "research_tool_calls": conduct_research_calls})

    except Exception as e:
        if is_token_limit_exceeded(e, configurable.supervisor_model):
            print(f"Token limit exceeded while reflecting: {e}")
        else:
            print(f"Other error in reflection phase: {e}")
    return Command(goto=END, update={"notes": get_notes_from_tool_calls(supervisor_messages), "research_brief": state.get("research_brief", "")})
