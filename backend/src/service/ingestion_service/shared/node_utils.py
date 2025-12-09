"""
Shared utilities for ingestion service.

This module contains common utilities used across all database indexers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Optional

from llama_index.core import StorageContext
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore

# Type-only imports for optional dependencies
if TYPE_CHECKING:
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
    from llama_index.vector_stores.elasticsearch import ElasticsearchStore
    from llama_index.vector_stores.qdrant import QdrantVectorStore

from src.service.ingestion_service.shared.metadata_utils import (
    build_chunk_id,
    sanitize_metadata,
)

logger = logging.getLogger(__name__)


def ensure_text_node(node: BaseNode) -> TextNode:
    """Convert any BaseNode to a TextNode."""
    if isinstance(node, TextNode):
        return node
    meta = dict(node.metadata or {})
    doc_id = meta.get("doc_id")
    chunk_index = meta.get("chunk_index")
    chunk_id = meta.get("chunk_id") or build_chunk_id(doc_id, chunk_index)
    if chunk_id:
        meta["id"] = chunk_id
        meta["chunk_id"] = chunk_id
    return TextNode(
        text=node.get_content(),
        metadata=meta,
        id_=meta.get("id"),
        relationships={},
    )


def clean_text_node(node: BaseNode, include_text_field: bool = False) -> TextNode:
    """Clean and normalize a node for indexing."""
    tn = ensure_text_node(node)
    meta = dict(tn.metadata or {})
    chunk_id = meta.get("chunk_id") or meta.get("id")
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)) if chunk_id else tn.id_
    meta["id"] = point_id
    if chunk_id:
        meta["chunk_id"] = chunk_id
    if include_text_field:
        meta["text"] = tn.get_content()
    meta = sanitize_metadata(meta, include_text=include_text_field)
    return TextNode(
        text=tn.get_content(),
        metadata=meta,
        id_=point_id,
        relationships={},
    )


def create_storage_context(
    qdrant_store: Optional["QdrantVectorStore"] = None,
    elasticsearch_store: Optional["ElasticsearchStore"] = None,
    neo4j_graph_store: Optional["Neo4jPropertyGraphStore"] = None,
    docstore: Optional[SimpleDocumentStore] = None,
) -> StorageContext:
    """Create a unified storage context for LlamaIndex."""
    logger.info("Creating unified storage context")

    if docstore is None:
        docstore = SimpleDocumentStore()

    primary_vector_store = qdrant_store or elasticsearch_store

    if primary_vector_store is None:
        logger.warning("No vector store provided to StorageContext")

    return StorageContext.from_defaults(
        vector_store=primary_vector_store,
        graph_store=neo4j_graph_store,  # type: ignore[arg-type]
        docstore=docstore,
    )


def await_maybe(coro_or_val):
    """Await a coroutine if needed, otherwise return the value."""
    if hasattr(coro_or_val, "__await__"):
        return asyncio.get_event_loop().run_until_complete(coro_or_val)
    return coro_or_val


def close_maybe_async(resource):
    """Close a resource that may be async."""
    if resource is None:
        return
    try:
        if hasattr(resource, "close"):
            await_maybe(resource.close())
    except Exception:
        pass
