"""
Knowledge Graph Schema.

Re-exports schema constants from the main settings module for
modular import organization.
"""

from src.service.ingestion_service.settings import (
    ALLOWED_NODES,
    ALLOWED_RELATIONSHIPS,
    CANONICAL_ENTITY_LOOKUP,
    ENTITY_ALIASES,
    EXCLUDED_METADATA_KEYS,
    KG_VALIDATION_SCHEMA,
)

__all__ = [
    "ALLOWED_NODES",
    "ALLOWED_RELATIONSHIPS",
    "KG_VALIDATION_SCHEMA",
    "ENTITY_ALIASES",
    "CANONICAL_ENTITY_LOOKUP",
    "EXCLUDED_METADATA_KEYS",
]
