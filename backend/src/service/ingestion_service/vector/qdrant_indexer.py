from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from src.service.ingestion_service import settings as ingestion_settings
from src.service.ingestion_service.shared.node_utils import (
    clean_text_node,
    close_maybe_async,
)


def create_qdrant_store(
    collection_name: Optional[str] = None,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> QdrantVectorStore:
    collection_name = collection_name or os.getenv("QDRANT_CLUSTER_ID", "documents")
    url = url or os.getenv("QDRANT_ENDPOINT", "http://localhost:6333")
    api_key = api_key or os.getenv("QDRANT_API_KEY")

    client_kwargs: Dict[str, Any] = {"url": url}
    if api_key:
        client_kwargs["api_key"] = api_key
    client = QdrantClient(**client_kwargs)

    if collection_name is None:
        raise ValueError("collection_name must be provided or set via QDRANT_CLUSTER_ID env var")

    if client and not client.collection_exists(collection_name):
        from qdrant_client.http import models

        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=ingestion_settings.EMBEDDING_DIMENSIONS,
                distance=models.Distance.COSINE,
            ),
        )

    return QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        store_text=False,
        store_nodes_override=True,
        enable_hybrid=False,
    )


def index_nodes_to_qdrant(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    collection_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
    batch_size: int = 20,
) -> Optional[QdrantVectorStore]:
    if not nodes:
        return None

    try:
        vector_store = create_qdrant_store(collection_name=collection_name)
        embedder = embed_model or Settings.embed_model

        if embedder is None:
            return None

        if upsert_doc_id:
            client = getattr(vector_store, "client", None)
            if client:
                try:
                    client.delete(
                        collection_name=vector_store.collection_name,
                        points_selector=Filter(
                            must=[
                                FieldCondition(
                                    key="doc_id",
                                    match=MatchValue(value=upsert_doc_id),
                                )
                            ]
                        ),
                    )
                except Exception:

                    pass
        pipeline = IngestionPipeline(
            transformations=[embedder],  # type: ignore[list-item]
            docstore=SimpleDocumentStore(),
            vector_store=vector_store,
        )

        cleaned_nodes = [clean_text_node(node, include_text_field=True) for node in nodes]
        total_nodes = len(cleaned_nodes)

        for i in range(0, total_nodes, batch_size):
            batch = cleaned_nodes[i : i + batch_size]
            try:
                pipeline.run(nodes=batch)
            except Exception as e:
                raise e

        close_maybe_async(getattr(vector_store, "client", None))
        return vector_store

    except Exception:
        return None
