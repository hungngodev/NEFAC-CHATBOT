"""LlamaIndex integration layer for the ingestion service."""

from src.service.ingestion_service.llamaindex.diagnostics import ensure_llamaindex_ready
from src.service.ingestion_service.llamaindex.metadata_utils import _get_base_metadata

__all__ = ["ensure_llamaindex_ready", "_get_base_metadata"]
