"""
LlamaIndex Observability Configuration.

Provides centralized observability setup using LlamaIndex's built-in
CallbackManager, LlamaDebugHandler, and TokenCountingHandler.

Usage:
    from src.service.ingestion_service.observability import (
        configure_observability,
        get_observability_stats,
        print_summary,
    )

    handlers = configure_observability(debug=True, count_tokens=True)
    # ... run pipeline ...
    print_summary(handlers)
"""

from .callback_config import (
    configure_observability,
    get_observability_stats,
    print_summary,
    reset_observability,
)

__all__ = [
    "configure_observability",
    "get_observability_stats",
    "print_summary",
    "reset_observability",
]
