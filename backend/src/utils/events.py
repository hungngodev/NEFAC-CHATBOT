from typing import Any, Dict

from langgraph.config import get_stream_writer

# Event Names
EVENT_FINAL_RESPONSE = "final_response_tag"
EVENT_DEEP_RESEARCH_UPDATE = "deep_research_update"


def emit_custom_event(name: str, data: Dict[str, Any]) -> None:
    """
    Emits a custom event using LangGraph's StreamWriter.
    This is used for stream_mode="custom".

    Args:
        name: The name of the event.
        data: The data payload for the event.
    """
    try:
        writer = get_stream_writer()
        writer({"name": name, "data": data})
    except Exception:
        # Fallback or log if writer is not available (e.g. not in a node context)
        # For now, we just pass to avoid crashing if called outside proper context
        pass
