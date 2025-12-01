from typing import Any, Optional

from langchain.chat_models import init_chat_model as _init_chat_model
from langchain_core.language_models import BaseChatModel

from src.config.models import SERVICE_TIER


def init_model(
    model: str,
    model_provider: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    disable_streaming: bool = False,
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
        disable_streaming: Whether to disable streaming
        **kwargs: Additional arguments passed to init_chat_model

    Returns:
        Configured BaseChatModel instance
    """

    # Prepare model_kwargs to inject service_tier
    # Note: Different providers might handle this differently.
    # For OpenAI, it's often passed in 'extra_body' or 'model_kwargs'.
    # The user's screenshot showed 'additional_kwargs={"service_tier": "flex"}'
    # but for LangChain's ChatOpenAI, it is typically 'model_kwargs={"extra_body": {"service_tier": ...}}'
    # or directly if supported.

    # However, based on the user's specific request and screenshot context (which looked like LlamaIndex but they asked for init_chat_model wrapper),
    # we will try to pass it in a way that LangChain accepts.

    # For ChatOpenAI in LangChain:
    # model_kwargs={"extra_body": {"service_tier": "flex"}} is the standard way for newer params.

    model_kwargs = kwargs.get("model_kwargs", {})
    if "extra_body" not in model_kwargs:
        model_kwargs["extra_body"] = {}

    # Only apply if it's an OpenAI model (heuristic check) or if we want it global
    # Assuming "flex" tier is an OpenAI concept for now.
    if "openai" in model or (model_provider and "openai" in model_provider):
        model_kwargs["extra_body"]["service_tier"] = SERVICE_TIER

    kwargs["model_kwargs"] = model_kwargs

    # Call the original function
    return _init_chat_model(model, model_provider=model_provider, temperature=temperature, max_tokens=max_tokens, disable_streaming=disable_streaming, **kwargs)
