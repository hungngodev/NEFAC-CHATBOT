from typing import Any, Optional

from langchain.chat_models import init_chat_model as _init_chat_model
from langchain_core.language_models import BaseChatModel

from src.config.models import DEFAULT_MAX_RETRIES, ENABLE_STREAMING, SERVICE_TIER


def init_model(
    model: str,
    model_provider: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    disable_streaming: Optional[bool] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Wrapper around langchain.chat_models.init_chat_model that injects
    the configured SERVICE_TIER into the model parameters.

    Args:
        model: The model name (e.g. "openai:gpt-4o")
        model_provider: Optional provider override
        temperature: Model temperature
        max_tokens: Max output tokens
        disable_streaming: Whether to disable streaming. If None, defaults to not ENABLE_STREAMING.
        **kwargs: Additional arguments passed to init_chat_model

    Returns:
        Configured BaseChatModel instance
    """
    if disable_streaming is None:
        disable_streaming = not ENABLE_STREAMING

    # Prepare extra_body to inject service_tier
    # The warning indicates 'extra_body' should be passed explicitly, not in model_kwargs.

    extra_body = kwargs.get("extra_body", {})

    # Only apply if it's an OpenAI model (heuristic check) or if we want it global
    # Assuming "flex" tier is an OpenAI concept for now.
    if "openai" in model or (model_provider and "openai" in model_provider):
        extra_body["service_tier"] = SERVICE_TIER

    if extra_body:
        kwargs["extra_body"] = extra_body

    # Call the original function
    if max_retries is None:
        max_retries = DEFAULT_MAX_RETRIES

    kwargs["max_retries"] = max_retries

    return _init_chat_model(model, model_provider=model_provider, temperature=temperature, max_tokens=max_tokens, disable_streaming=disable_streaming, **kwargs)
