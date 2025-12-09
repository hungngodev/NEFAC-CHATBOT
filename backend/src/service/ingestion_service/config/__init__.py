"""
LlamaIndex Configuration Module.

Centralized configuration for LlamaIndex Settings and KG schema.

Usage:
    from src.service.ingestion_service.config import (
        configure_llamaindex,
        ALLOWED_NODES,
        ALLOWED_RELATIONSHIPS,
    )

    configure_llamaindex()  # Call once at startup
"""

from .schema import (
    ALLOWED_NODES,
    ALLOWED_RELATIONSHIPS,
    CANONICAL_ENTITY_LOOKUP,
    ENTITY_ALIASES,
    KG_VALIDATION_SCHEMA,
)
from .settings_config import configure_llamaindex

__all__ = [
    "configure_llamaindex",
    "ALLOWED_NODES",
    "ALLOWED_RELATIONSHIPS",
    "KG_VALIDATION_SCHEMA",
    "ENTITY_ALIASES",
    "CANONICAL_ENTITY_LOOKUP",
]
