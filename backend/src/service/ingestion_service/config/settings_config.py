from __future__ import annotations

import os
from typing import Any, Dict, Optional

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI


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
    api_key = api_key or os.getenv("OPENAI_API_KEY")

    if not api_key:

        pass
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

    Settings.embed_model = OpenAIEmbedding(
        model=embedding_model,
        dimensions=embedding_dimensions,
        api_key=api_key,
    )

    Settings.chunk_size = chunk_size
    Settings.chunk_overlap = chunk_overlap


def get_llm():
    return Settings.llm


def get_embed_model():
    return Settings.embed_model
