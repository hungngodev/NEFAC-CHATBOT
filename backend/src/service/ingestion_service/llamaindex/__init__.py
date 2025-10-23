"""LlamaIndex integration layer for the ingestion service."""

from .diagnostics import ensure_llamaindex_ready

__all__ = ["ensure_llamaindex_ready"]
