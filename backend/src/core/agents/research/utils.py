from typing import Any

from src.utils.events import EVENT_DEEP_RESEARCH_UPDATE, emit_custom_event


def calculate_progress(current_loop: int, max_loops: int, current_step: int, max_steps: int) -> float:
    """Calculates the global progress percentage for the deep research process."""
    current_loop_val = max(1, current_loop)
    max_loops_val = max(1, max_loops)
    max_steps_val = max(1, max_steps)

    try:
        base_progress = 10 + ((current_loop_val - 1) / max_loops_val) * 80
        step_progress = current_step / max_steps_val
        loop_chunk = 80 / max_loops_val
        global_progress = min(90, base_progress + (step_progress * loop_chunk))
        return global_progress
    except ZeroDivisionError:
        return 0.0


def emit_research_status(
    status: str,
    current_loop: int = 0,
    max_loops: int = 1,
    current_step: int = 0,
    max_steps: int = 1,
    include_progress: bool = False,
) -> dict[str, Any]:
    """Emits a deep research status update event and returns the payload."""
    payload: dict[str, Any] = {"status": status}

    if include_progress:
        progress = calculate_progress(current_loop, max_loops, current_step, max_steps)
        # Crude estimation logic retained from original code
        estimated_time = max(60, 600 - (current_loop * 150) - (current_step * 10))

        payload.update(
            {
                "progress": progress,
                "total_steps": 100,
                "estimated_time_remaining": estimated_time,
            }
        )

    emit_custom_event(EVENT_DEEP_RESEARCH_UPDATE, payload)
    return payload
