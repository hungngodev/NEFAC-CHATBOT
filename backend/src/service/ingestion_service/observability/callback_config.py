from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
