from typing import Any, Optional

from langchain.chat_models import init_chat_model as _init_chat_model
from langchain_core.language_models import BaseChatModel

from src.config.models import DEFAULT_MAX_RETRIES, ENABLE_STREAMING, SERVICE_TIER, ModelType
from src.config.node_names import INTERNAL_NODES


def init_model(
    model: ModelType,
    model_provider: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    disable_streaming: Optional[bool] = None,
    node_name: Optional[str] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Initialize a chat model with the given configuration.

    Args:
        model: The model type to use (e.g., "openai:gpt-4o")
        model_provider: Optional provider override
        temperature: The temperature for generation (default: 0)
        max_tokens: Max output tokens
        max_retries: Max retries (defaults to DEFAULT_MAX_RETRIES)
        disable_streaming: Whether to disable streaming. If None, defaults to not ENABLE_STREAMING.
        node_name: The name of the node using this model. Used to check against INTERNAL_NODES.
        **kwargs: Additional arguments passed to init_chat_model

    Returns:
        A configured ChatOpenAI or ChatAnthropic instance.
    """
    if disable_streaming is None:
        if node_name and node_name in INTERNAL_NODES:
            disable_streaming = True
        else:
            disable_streaming = not ENABLE_STREAMING

    if max_retries is None:
        max_retries = DEFAULT_MAX_RETRIES

    # Inject service tier if not present
    # Only apply if it's an OpenAI model (heuristic check) or if we want it global
    extra_body = kwargs.get("extra_body", {})
    if "openai" in model or (model_provider and "openai" in model_provider):
        extra_body["service_tier"] = SERVICE_TIER

    if extra_body:
        kwargs["extra_body"] = extra_body

    return _init_chat_model(
        model,
        model_provider=model_provider,
        temperature=temperature,
        max_tokens=max_tokens,
        disable_streaming=disable_streaming,
        max_retries=max_retries,
        **kwargs,
    )
