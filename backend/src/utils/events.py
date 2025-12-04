from typing import Any, Dict, Optional
from langgraph.config import get_stream_writer

# Event Names
EVENT_FINAL_RESPONSE = "final_response_tag"

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
    except Exception as e:
        # Fallback or log if writer is not available (e.g. not in a node context)
        # For now, we just pass to avoid crashing if called outside proper context
        pass

def emit_final_response_signal(is_final: bool = True) -> None:
    """
    Helper to emit the final response signal.
    
    Args:
        is_final: Whether the upcoming response is the final one.
    """
    emit_custom_event(EVENT_FINAL_RESPONSE, {"is_final": is_final})
