from __future__ import annotations

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


def create_elasticsearch_store(
    index_name: Optional[str] = None,
    es_url: Optional[str] = None,
) -> ElasticsearchStore:
    index_name = index_name or os.getenv("ES_INDEX", "documents")
    es_url = es_url or os.getenv("ES_HOST", "http://localhost:9200")

    try:
        if index_name is None:
            raise ValueError("index_name must be provided or set via ES_INDEX env var")
        return ElasticsearchStore(
            index_name=index_name,
            es_url=es_url,
            retrieval_strategy=AsyncBM25Strategy(),
        )
    except ImportError:
        raise


async def index_nodes_to_elasticsearch(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    index_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
) -> Optional[ElasticsearchStore]:
    if not nodes:
        return None

    vector_store = create_elasticsearch_store(index_name=index_name)
    client = getattr(vector_store, "client", None)

    if upsert_doc_id and client:
        try:
            resp = client.delete_by_query(
                index=vector_store.index_name,
                body={"query": {"term": {"doc_id": upsert_doc_id}}},
                ignore_unavailable=True,
            )
            if hasattr(resp, "__await__"):
                await resp
        except Exception:

            pass
    try:
        cleaned_nodes = [clean_text_node(node, include_text_field=True) for node in nodes]
        await vector_store.async_add(cleaned_nodes)  # type: ignore[arg-type]

        close_maybe_async(getattr(vector_store, "client", None))
        return vector_store
    except Exception:
        return None
