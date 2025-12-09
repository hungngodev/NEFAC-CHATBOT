"""
Ingestion Service Package

Modular LlamaIndex ingestion infrastructure with:
- config/        - LlamaIndex Settings configuration
- observability/ - CallbackManager, TokenCountingHandler, LlamaDebugHandler
- pipeline/      - IngestionPipelineBuilder with caching and deduplication
- vector/        - Qdrant vector database indexing
- keyword/       - Elasticsearch keyword search indexing
- graph/         - Neo4j property graph indexing
- shared/        - Common utilities
- loader/        - Document loading
- orchestration/ - Workflow coordination

Usage:
    from src.service.ingestion_service import (
        configure_llamaindex,
        configure_observability,
        IngestionPipelineBuilder,
    )

    # 1. Configure
    configure_llamaindex()
    handlers = configure_observability()

    # 2. Build pipeline
    pipeline = (
        IngestionPipelineBuilder()
        .with_chunking()
        .with_deduplication()
        .with_caching()
        .with_embeddings()
        .build()
    )

    # 3. Run
    nodes = pipeline.run(documents, num_workers=4)
"""

# Config module - LlamaIndex Settings
from .config import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, configure_llamaindex

# Observability module - Replaces PipelineTracker
from .observability import (
    configure_observability,
    get_observability_stats,
    print_summary,
)

# Pipeline module - Builder pattern for IngestionPipeline
from .pipeline import IngestionPipelineBuilder

__all__ = [
    # Config
    "configure_llamaindex",
    "ALLOWED_NODES",
    "ALLOWED_RELATIONSHIPS",
    # Observability
    "configure_observability",
    "get_observability_stats",
    "print_summary",
    # Pipeline
    "IngestionPipelineBuilder",
]
