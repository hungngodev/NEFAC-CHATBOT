from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler

TIKTOKEN_AVAILABLE = False
TOKEN_HANDLER_AVAILABLE = False
LANGFUSE_AVAILABLE = False

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    pass

try:
    from llama_index.core.callbacks import TokenCountingHandler

    TOKEN_HANDLER_AVAILABLE = True
except ImportError:
    pass

try:
    from langfuse import get_client
    from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

    LANGFUSE_AVAILABLE = True
except ImportError:
    pass


@dataclass
class ObservabilityStats:
    prompt_llm_tokens: int = 0
    completion_llm_tokens: int = 0
    total_llm_tokens: int = 0
    total_embedding_tokens: int = 0
    llm_calls: int = 0
    embedding_calls: int = 0


_global_handlers: Dict[str, Any] = {}
_instrumented = False


def configure_observability(
    debug: bool = True,
    count_tokens: bool = True,
    model: str = "gpt-4o-mini",
    print_trace: bool = False,
    enable_langfuse: bool = True,
) -> Dict[str, Any]:
    global _global_handlers, _instrumented
    handlers: List[Any] = []
    result: Dict[str, Any] = {}

    if enable_langfuse and LANGFUSE_AVAILABLE and not _instrumented:
        try:
            langfuse = get_client()
            if langfuse.auth_check():
                LlamaIndexInstrumentor().instrument()
                _instrumented = True
                result["langfuse"] = True
                print("✅ Langfuse observability enabled - traces at cloud.langfuse.com")
        except Exception:
            pass

    if debug:
        debug_handler = LlamaDebugHandler(print_trace_on_end=print_trace)
        handlers.append(debug_handler)
        result["debug_handler"] = debug_handler

    if count_tokens and TIKTOKEN_AVAILABLE and TOKEN_HANDLER_AVAILABLE:
        try:
            tokenizer = tiktoken.encoding_for_model(model)
            token_counter = TokenCountingHandler(
                tokenizer=tokenizer.encode,
                verbose=False,
            )
            handlers.append(token_counter)
            result["token_counter"] = token_counter
        except Exception:
            pass

    if handlers:
        callback_manager = CallbackManager(handlers)
        Settings.callback_manager = callback_manager

    _global_handlers = result
    return result


def get_observability_stats(handlers: Optional[Dict[str, Any]] = None) -> ObservabilityStats:
    if handlers is None:
        handlers = _global_handlers

    stats = ObservabilityStats()

    if handlers.get("token_counter"):
        tc = handlers["token_counter"]
        stats.prompt_llm_tokens = getattr(tc, "prompt_llm_token_count", 0)
        stats.completion_llm_tokens = getattr(tc, "completion_llm_token_count", 0)
        stats.total_llm_tokens = getattr(tc, "total_llm_token_count", 0)
        stats.total_embedding_tokens = getattr(tc, "total_embedding_token_count", 0)

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
    stats = get_observability_stats(handlers)

    print("\n" + "=" * 80)
    print("📊 INGESTION PIPELINE SUMMARY")
    print("=" * 80)

    print("\n🎯 TOKEN USAGE:")
    print(f"  Prompt tokens:     {stats.prompt_llm_tokens:,}")
    print(f"  Completion tokens: {stats.completion_llm_tokens:,}")
    print(f"  Total LLM tokens:  {stats.total_llm_tokens:,}")
    print(f"  Embedding tokens:  {stats.total_embedding_tokens:,}")

    input_cost = (stats.prompt_llm_tokens / 1_000_000) * 0.15
    output_cost = (stats.completion_llm_tokens / 1_000_000) * 0.60
    embedding_cost = (stats.total_embedding_tokens / 1_000_000) * 0.02
    total_cost = input_cost + output_cost + embedding_cost

    print("\n💰 ESTIMATED COST:")
    print(f"  Input:     ${input_cost:.4f}")
    print(f"  Output:    ${output_cost:.4f}")
    print(f"  Embedding: ${embedding_cost:.4f}")
    print(f"  Total:     ${total_cost:.4f}")

    print("\n🔄 API CALLS:")
    print(f"  LLM calls:       {stats.llm_calls}")
    print(f"  Embedding calls: {stats.embedding_calls}")

    print("=" * 80)


def reset_observability() -> None:
    global _global_handlers

    if _global_handlers.get("token_counter"):
        tc = _global_handlers["token_counter"]
        tc.reset_counts()

    if _global_handlers.get("debug_handler"):
        dh = _global_handlers["debug_handler"]
        dh.flush_event_logs()

    _global_handlers = {}
    Settings.callback_manager = None  # type: ignore[assignment]


def get_llm_events(handlers: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if handlers is None:
        handlers = _global_handlers

    if handlers.get("debug_handler"):
        try:
            return handlers["debug_handler"].get_llm_inputs_outputs()
        except Exception:
            return []
    return []


_module_logger = logging.getLogger("ingestion_service")

_langfuse_observe = None
_langfuse_propagate = None
_langfuse_get_client = None

if LANGFUSE_AVAILABLE:
    try:
        from langfuse import get_client as _get_langfuse
        from langfuse import observe as _observe
        from langfuse import propagate_attributes as _propagate

        _test = _get_langfuse()
        if _test and _test.auth_check():
            _langfuse_observe = _observe
            _langfuse_propagate = _propagate
            _langfuse_get_client = _get_langfuse
    except Exception:
        pass


F = TypeVar("F", bound=Callable[..., Any])


def observe(name: Optional[str] = None, **kwargs: Any) -> Callable[[F], F]:
    """Decorator to trace function execution with Langfuse.

    Falls back to no-op if Langfuse is unavailable.
    """
    if _langfuse_observe:
        return _langfuse_observe(name=name, **kwargs)

    def decorator(func: F) -> F:
        return func

    return decorator


class _NoOpContext:
    """No-op context manager for when Langfuse is unavailable."""

    def __enter__(self) -> "_NoOpContext":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def propagate_attributes(**kwargs: Any) -> Any:
    """Context manager to propagate Langfuse attributes.

    Falls back to no-op if Langfuse is unavailable.
    """
    if _langfuse_propagate:
        return _langfuse_propagate(**kwargs)
    return _NoOpContext()


def _update_langfuse_span(metadata: Optional[Dict[str, Any]] = None, level: str = "DEFAULT") -> None:
    """Update current Langfuse span with metadata if available."""
    if not LANGFUSE_AVAILABLE or not metadata:
        return
    try:
        if _langfuse_get_client:
            client = _langfuse_get_client()
            if client:
                client.update_current_span(metadata=metadata, level=level)
    except Exception:
        pass


def log_error(
    message: str,
    *,
    error: Optional[Exception] = None,
    doc_id: Optional[str] = None,
    node_id: Optional[str] = None,
    stage: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an error to both Python logger and Langfuse.

    Args:
        message: Human-readable error message
        error: The exception that occurred
        doc_id: Document ID for tracking
        node_id: Node/chunk ID for tracking
        stage: Pipeline stage where error occurred
        extra: Additional metadata for Langfuse
    """
    context_parts = []
    if doc_id:
        context_parts.append(f"doc_id={doc_id}")
    if node_id:
        context_parts.append(f"node_id={node_id}")
    if stage:
        context_parts.append(f"stage={stage}")

    context = f" [{', '.join(context_parts)}]" if context_parts else ""
    error_str = f": {error}" if error else ""
    full_message = f"{message}{context}{error_str}"

    _module_logger.error(full_message)

    metadata: Dict[str, Any] = {"error": message}
    if doc_id:
        metadata["doc_id"] = doc_id
    if node_id:
        metadata["node_id"] = node_id
    if stage:
        metadata["stage"] = stage
    if error:
        metadata["error_detail"] = str(error)
    if extra:
        metadata.update(extra)

    _update_langfuse_span(metadata, level="ERROR")


def log_warning(
    message: str,
    *,
    error: Optional[Exception] = None,
    doc_id: Optional[str] = None,
    node_id: Optional[str] = None,
    stage: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a warning to both Python logger and Langfuse."""
    context_parts = []
    if doc_id:
        context_parts.append(f"doc_id={doc_id}")
    if node_id:
        context_parts.append(f"node_id={node_id}")
    if stage:
        context_parts.append(f"stage={stage}")

    context = f" [{', '.join(context_parts)}]" if context_parts else ""
    error_str = f": {error}" if error else ""
    full_message = f"{message}{context}{error_str}"

    _module_logger.warning(full_message)

    metadata: Dict[str, Any] = {"warning": message}
    if doc_id:
        metadata["doc_id"] = doc_id
    if node_id:
        metadata["node_id"] = node_id
    if stage:
        metadata["stage"] = stage
    if error:
        metadata["error_detail"] = str(error)
    if extra:
        metadata.update(extra)

    _update_langfuse_span(metadata, level="WARNING")


def log_debug(
    message: str,
    *,
    error: Optional[Exception] = None,
    doc_id: Optional[str] = None,
    node_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log debug info to Python logger only (not sent to Langfuse)."""
    context_parts = []
    if doc_id:
        context_parts.append(f"doc_id={doc_id}")
    if node_id:
        context_parts.append(f"node_id={node_id}")

    context = f" [{', '.join(context_parts)}]" if context_parts else ""
    error_str = f": {error}" if error else ""
    full_message = f"{message}{context}{error_str}"

    _module_logger.debug(full_message)
