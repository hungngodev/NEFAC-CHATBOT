from typing import Any

from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event


def emit_research_status(status: str) -> dict[str, Any]:
    """Emits a deep research status update event and returns the payload."""
    payload: dict[str, Any] = {"status": status}
    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, payload)
    return payload
