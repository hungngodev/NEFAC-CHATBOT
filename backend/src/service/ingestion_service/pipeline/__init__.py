"""
LlamaIndex Ingestion Pipeline Module.

Provides modular pipeline construction with:
- IngestionPipelineBuilder: Fluent builder pattern
- IngestionCache: Transform caching
- SimpleDocumentStore + DocstoreStrategy: Document deduplication
- Pipeline persistence: Save/load state across runs

Usage:
    from src.service.ingestion_service.pipeline import IngestionPipelineBuilder

    pipeline = (
        IngestionPipelineBuilder()
        .with_chunking()
        .with_caching()
        .with_deduplication()
        .with_embeddings()
        .build()
    )
"""

from .builder import IngestionPipelineBuilder
from .cache import (
    create_docstore,
    create_ingestion_cache,
    load_pipeline_state,
    save_pipeline_state,
)

__all__ = [
    "IngestionPipelineBuilder",
    "create_ingestion_cache",
    "create_docstore",
    "load_pipeline_state",
    "save_pipeline_state",
]
