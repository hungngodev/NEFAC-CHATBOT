"""
LlamaIndex Settings Configuration.

Provides a single function to configure all LlamaIndex global settings.
Call once at application startup.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

logger = logging.getLogger(__name__)


def configure_llamaindex(
    model: str = "gpt-4o-mini",
    embedding_model: str = "text-embedding-3-small",
    embedding_dimensions: int = 1536,
    chunk_size: int = 384,
    chunk_overlap: int = 38,
    max_retries: int = 30,
    timeout: float = 900.0,
    temperature: float = 0.0,
    api_key: Optional[str] = None,
    service_tier: Optional[str] = None,
) -> None:
    """
    Configure LlamaIndex global Settings.

    Call this once at application startup. All LlamaIndex components
    will use these settings by default.

    Args:
        model: OpenAI model for LLM calls
        embedding_model: OpenAI embedding model
        embedding_dimensions: Embedding vector dimensions
        chunk_size: Default chunk size for node parsing
        chunk_overlap: Default chunk overlap
        max_retries: Max retries for API calls
        timeout: Timeout for API calls in seconds
        temperature: LLM temperature (0=deterministic)
        api_key: OpenAI API key (default: OPENAI_API_KEY env var)
        service_tier: OpenAI service tier (e.g., "flex")

    Example:
        from src.service.ingestion_service.config import configure_llamaindex
        configure_llamaindex(model="gpt-4o-mini", chunk_size=512)
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")

    if not api_key:
        logger.warning("OPENAI_API_KEY not set, LLM calls may fail")

    # Configure LLM
    llm_kwargs: Dict[str, Any] = {
        "model": model,
        "max_retries": max_retries,
        "timeout": timeout,
        "temperature": temperature,
        "api_key": api_key,
    }
    if service_tier:
        llm_kwargs["additional_kwargs"] = {"service_tier": service_tier}

    Settings.llm = OpenAI(**llm_kwargs)

    # Configure embeddings
    Settings.embed_model = OpenAIEmbedding(
        model=embedding_model,
        dimensions=embedding_dimensions,
        api_key=api_key,
    )

    # Configure chunking defaults
    Settings.chunk_size = chunk_size
    Settings.chunk_overlap = chunk_overlap

    logger.info(f"✅ LlamaIndex configured: " f"llm={model}, embed={embedding_model}, " f"chunk_size={chunk_size}")


def get_llm():
    """Get the configured LLM from Settings."""
    return Settings.llm


def get_embed_model():
    """Get the configured embedding model from Settings."""
    return Settings.embed_model
