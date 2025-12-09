"""
LlamaIndex CallbackManager Configuration.

Replaces the custom PipelineTracker with LlamaIndex's built-in observability:
- LlamaDebugHandler: Traces all LLM/embedding calls
- TokenCountingHandler: Tracks token usage for cost analysis

This provides automatic tracing without manual log_phase_start/end calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler

logger = logging.getLogger(__name__)

# Try to import tiktoken for token counting
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.info("tiktoken not installed. Token counting will be disabled.")

# Try to import TokenCountingHandler
try:
    from llama_index.core.callbacks import TokenCountingHandler

    TOKEN_HANDLER_AVAILABLE = True
except ImportError:
    TOKEN_HANDLER_AVAILABLE = False
    logger.info("TokenCountingHandler not available in this LlamaIndex version.")


@dataclass
class ObservabilityStats:
    """Statistics collected from observability handlers."""

    prompt_llm_tokens: int = 0
    completion_llm_tokens: int = 0
    total_llm_tokens: int = 0
    total_embedding_tokens: int = 0
    llm_calls: int = 0
    embedding_calls: int = 0


_global_handlers: Dict[str, Any] = {}


def configure_observability(
    debug: bool = True,
    count_tokens: bool = True,
    model: str = "gpt-4o-mini",
    print_trace: bool = False,
) -> Dict[str, Any]:
    """
    Configure LlamaIndex observability handlers.

    This replaces the manual PipelineTracker with LlamaIndex's built-in
    observability system. Call once at application startup.

    Args:
        debug: Enable LlamaDebugHandler for event tracing
        count_tokens: Enable TokenCountingHandler for token tracking
        model: Model name for tiktoken encoding
        print_trace: Print trace on every event completion

    Returns:
        Dictionary of configured handlers for later stats retrieval

    Example:
        handlers = configure_observability()
        # ... run your pipeline ...
        print_summary(handlers)
    """
    global _global_handlers
    handlers: List[Any] = []
    result: Dict[str, Any] = {}

    # 1. Debug Handler - traces all LLM/embedding calls
    if debug:
        debug_handler = LlamaDebugHandler(print_trace_on_end=print_trace)
        handlers.append(debug_handler)
        result["debug_handler"] = debug_handler
        logger.info("✅ LlamaDebugHandler enabled for event tracing")

    # 2. Token Counter - tracks token usage for cost analysis
    if count_tokens and TIKTOKEN_AVAILABLE and TOKEN_HANDLER_AVAILABLE:
        try:
            tokenizer = tiktoken.encoding_for_model(model)
            token_counter = TokenCountingHandler(
                tokenizer=tokenizer.encode,
                verbose=False,
            )
            handlers.append(token_counter)
            result["token_counter"] = token_counter
            logger.info("✅ TokenCountingHandler enabled for token tracking")
        except Exception as e:
            logger.warning(f"Failed to initialize TokenCountingHandler: {e}")
    elif count_tokens:
        logger.warning("Token counting requested but tiktoken/handler not available")

    # 3. Register globally with LlamaIndex Settings
    if handlers:
        callback_manager = CallbackManager(handlers)
        Settings.callback_manager = callback_manager
        logger.info(f"✅ CallbackManager registered with {len(handlers)} handlers")

    _global_handlers = result
    return result


def get_observability_stats(handlers: Optional[Dict[str, Any]] = None) -> ObservabilityStats:
    """
    Get accumulated statistics from observability handlers.

    Args:
        handlers: Handler dict from configure_observability(), or None to use global

    Returns:
        ObservabilityStats dataclass with token and call counts
    """
    if handlers is None:
        handlers = _global_handlers

    stats = ObservabilityStats()

    # Token counting stats
    if handlers.get("token_counter"):
        tc = handlers["token_counter"]
        stats.prompt_llm_tokens = getattr(tc, "prompt_llm_token_count", 0)
        stats.completion_llm_tokens = getattr(tc, "completion_llm_token_count", 0)
        stats.total_llm_tokens = getattr(tc, "total_llm_token_count", 0)
        stats.total_embedding_tokens = getattr(tc, "total_embedding_token_count", 0)

    # Debug handler stats
    if handlers.get("debug_handler"):
        dh = handlers["debug_handler"]
        try:
            stats.llm_calls = len(dh.get_llm_inputs_outputs())
        except Exception:
            stats.llm_calls = 0
        try:
            stats.embedding_calls = len(dh.get_event_pairs("embedding"))
        except Exception:
            stats.embedding_calls = 0

    return stats


def print_summary(handlers: Optional[Dict[str, Any]] = None) -> None:
    """
    Print a clean summary of observability data.

    This replaces the old PipelineTracker.log_summary() method with
    data from LlamaIndex's built-in handlers.

    Args:
        handlers: Handler dict from configure_observability(), or None to use global
    """
    stats = get_observability_stats(handlers)

    separator = "=" * 80
    logger.info(f"\n{separator}")
    logger.info("📊 INGESTION PIPELINE SUMMARY (LlamaIndex Observability)")
    logger.info(separator)

    # Token usage
    logger.info("\n🎯 TOKEN USAGE:")
    logger.info(f"  Prompt tokens:     {stats.prompt_llm_tokens:,}")
    logger.info(f"  Completion tokens: {stats.completion_llm_tokens:,}")
    logger.info(f"  Total LLM tokens:  {stats.total_llm_tokens:,}")
    logger.info(f"  Embedding tokens:  {stats.total_embedding_tokens:,}")

    # Estimated cost (GPT-4o-mini pricing as of Dec 2024)
    # Input: $0.150/1M tokens, Output: $0.600/1M tokens
    input_cost = (stats.prompt_llm_tokens / 1_000_000) * 0.15
    output_cost = (stats.completion_llm_tokens / 1_000_000) * 0.60
    embedding_cost = (stats.total_embedding_tokens / 1_000_000) * 0.02  # text-embedding-3-small
    total_cost = input_cost + output_cost + embedding_cost

    logger.info("\n💰 ESTIMATED COST (GPT-4o-mini + text-embedding-3-small):")
    logger.info(f"  Input:     ${input_cost:.4f}")
    logger.info(f"  Output:    ${output_cost:.4f}")
    logger.info(f"  Embedding: ${embedding_cost:.4f}")
    logger.info(f"  Total:     ${total_cost:.4f}")

    # API calls
    logger.info("\n🔄 API CALLS:")
    logger.info(f"  LLM calls:       {stats.llm_calls}")
    logger.info(f"  Embedding calls: {stats.embedding_calls}")

    logger.info(separator)


def reset_observability() -> None:
    """Reset all observability handlers and counters."""
    global _global_handlers

    if _global_handlers.get("token_counter"):
        tc = _global_handlers["token_counter"]
        tc.reset_counts()

    if _global_handlers.get("debug_handler"):
        dh = _global_handlers["debug_handler"]
        dh.flush_event_logs()

    _global_handlers = {}
    Settings.callback_manager = None  # type: ignore[assignment]
    logger.info("Observability handlers reset")


def get_llm_events(handlers: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Get detailed LLM call events for debugging.

    Args:
        handlers: Handler dict or None for global

    Returns:
        List of LLM input/output event dictionaries
    """
    if handlers is None:
        handlers = _global_handlers

    if handlers.get("debug_handler"):
        try:
            return handlers["debug_handler"].get_llm_inputs_outputs()
        except Exception:
            return []
    return []
