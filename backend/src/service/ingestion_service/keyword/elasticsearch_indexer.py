"""
Elasticsearch keyword database indexer.

Handles indexing documents to Elasticsearch for BM25 keyword search.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from llama_index.core.schema import BaseNode
from llama_index.vector_stores.elasticsearch import (
    AsyncBM25Strategy,
    ElasticsearchStore,
)

from src.service.ingestion_service.shared.node_utils import (
    clean_text_node,
    close_maybe_async,
)

logger = logging.getLogger(__name__)


def create_elasticsearch_store(
    index_name: Optional[str] = None,
    es_url: Optional[str] = None,
) -> ElasticsearchStore:
    """
    Create an Elasticsearch store connection with BM25 strategy.

    Args:
        index_name: Name of the index (defaults to ES_INDEX env var)
        es_url: Elasticsearch URL (defaults to ES_HOST env var)

    Returns:
        Configured ElasticsearchStore instance
    """
    index_name = index_name or os.getenv("ES_INDEX", "documents")
    es_url = es_url or os.getenv("ES_HOST", "http://localhost:9200")

    logger.info(f"Creating Elasticsearch store: {index_name} with strategy: bm25")

    try:
        # Ensure index_name is not None
        if index_name is None:
            raise ValueError("index_name must be provided or set via ES_INDEX env var")
        return ElasticsearchStore(
            index_name=index_name,
            es_url=es_url,
            retrieval_strategy=AsyncBM25Strategy(),
        )
    except ImportError as e:
        logger.error(f"Failed to import Elasticsearch strategies: {e}")
        raise


async def index_nodes_to_elasticsearch(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    index_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
) -> Optional[ElasticsearchStore]:
    """
    Index nodes to Elasticsearch with BM25 strategy.

    Args:
        nodes: List of nodes to index
        embed_model: Not used for BM25, kept for API compatibility
        index_name: Target index name
        upsert_doc_id: If provided, delete existing docs with this ID first

    Returns:
        ElasticsearchStore instance if successful, None otherwise
    """
    if not nodes:
        logger.warning("No nodes to index to Elasticsearch")
        return None

    vector_store = create_elasticsearch_store(index_name=index_name)
    client = getattr(vector_store, "client", None)

    # Delete existing documents if upserting
    if upsert_doc_id and client:
        try:
            resp = client.delete_by_query(
                index=vector_store.index_name,
                body={"query": {"term": {"doc_id": upsert_doc_id}}},
                ignore_unavailable=True,
            )
            if hasattr(resp, "__await__"):
                await resp
            logger.info("Deleted existing Elasticsearch docs for doc_id=%s", upsert_doc_id)
        except Exception as exc:
            logger.debug("Delete ES docs skipped for doc_id=%s: %s", upsert_doc_id, exc)

    try:
        cleaned_nodes = [clean_text_node(node, include_text_field=True) for node in nodes]
        await vector_store.async_add(cleaned_nodes)  # type: ignore[arg-type]

        logger.info(f"✅ Indexed {len(cleaned_nodes)} nodes to Elasticsearch")
        close_maybe_async(getattr(vector_store, "client", None))
        return vector_store
    except Exception as exc:
        logger.error("Failed to index to Elasticsearch: %s", exc)
        return None
