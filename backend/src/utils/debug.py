import os


def get_debug_mode() -> bool:
    """
    Returns True if ENABLE_LANGGRAPH_DEBUG_LOGS environment variable is set to 'true' (case-insensitive).
    """
    return os.getenv("ENABLE_LANGGRAPH_DEBUG_LOGS", "").lower() == "true"
