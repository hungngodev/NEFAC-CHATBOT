from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional

from llama_index.core import Settings, StorageContext
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.vector_stores.elasticsearch import (
    AsyncBM25Strategy,
    ElasticsearchStore,
)
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from src.service.ingestion_service import settings as ingestion_settings
from src.service.ingestion_service.graph.property_graph_ingestor import LegalPropertyGraphIngestor
from src.service.ingestion_service.llamaindex.metadata_utils import build_chunk_id, sanitize_metadata


def _ensure_text_node(node: BaseNode) -> TextNode:
    if isinstance(node, TextNode):
        return node
    meta = dict(node.metadata or {})
    doc_id = meta.get("doc_id")
    chunk_index = meta.get("chunk_index")
    chunk_id = meta.get("chunk_id") or build_chunk_id(doc_id, chunk_index)
    if chunk_id:
        meta["id"] = chunk_id
        meta["chunk_id"] = chunk_id
    return TextNode(text=node.get_content(), metadata=meta, id_=meta.get("id"), relationships={})


def _clean_text_node(node: BaseNode, include_text_field: bool = False) -> TextNode:
    tn = _ensure_text_node(node)
    meta = dict(tn.metadata or {})
    chunk_id = meta.get("chunk_id") or meta.get("id")
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)) if chunk_id else tn.id_
    meta["id"] = point_id
    if chunk_id:
        meta["chunk_id"] = chunk_id
    if include_text_field:
        meta["text"] = tn.get_content()
    meta = sanitize_metadata(meta, include_text=include_text_field)
    return TextNode(text=tn.get_content(), metadata=meta, id_=point_id, relationships={})


def create_storage_context(
    qdrant_store: Optional[QdrantVectorStore] = None,
    elasticsearch_store: Optional[ElasticsearchStore] = None,
    neo4j_graph_store: Optional[Neo4jPropertyGraphStore] = None,
    docstore: Optional[SimpleDocumentStore] = None,
) -> StorageContext:

    if docstore is None:
        docstore = SimpleDocumentStore()

    primary_vector_store = qdrant_store or elasticsearch_store

    if primary_vector_store is None:

        pass
    return StorageContext.from_defaults(
        vector_store=primary_vector_store,
        graph_store=neo4j_graph_store,  # type: ignore[arg-type]
        docstore=docstore,
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
            vectors_config=models.VectorParams(size=ingestion_settings.EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE),
        )

    return QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        store_text=False,
        store_nodes_override=True,
        enable_hybrid=False,
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


def _await_maybe(coro_or_val):
    if hasattr(coro_or_val, "__await__"):
        return asyncio.get_event_loop().run_until_complete(coro_or_val)
    return coro_or_val


def _close_maybe_async(resource):
    if resource is None:
        return
    try:
        if hasattr(resource, "close"):
            _await_maybe(resource.close())
    except Exception:
        pass


def index_nodes_to_qdrant(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    collection_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
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
                        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=upsert_doc_id))]),
                    )
                except Exception:

                    pass
        pipeline = IngestionPipeline(
            transformations=[
                embedder,  # type: ignore[list-item]
            ],
            docstore=SimpleDocumentStore(),
            vector_store=vector_store,
        )

        cleaned_nodes = [_clean_text_node(node, include_text_field=True) for node in nodes]
        batch_size = 20
        total_nodes = len(cleaned_nodes)

        for i in range(0, total_nodes, batch_size):
            batch = cleaned_nodes[i : i + batch_size]
            try:
                pipeline.run(nodes=batch)
            except Exception as e:
                raise e

        _close_maybe_async(getattr(vector_store, "client", None))
        return vector_store

    except Exception:
        return None


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
        cleaned_nodes = [_clean_text_node(node, include_text_field=True) for node in nodes]
        await vector_store.async_add(cleaned_nodes)  # type: ignore[arg-type]

        _close_maybe_async(getattr(vector_store, "client", None))
        return vector_store
    except Exception:
        return None


def index_nodes_to_neo4j(
    nodes: List[BaseNode],
    use_property_graph: bool = True,
    upsert_doc_id: Optional[str] = None,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
) -> int:
    if not nodes:
        return 0

    try:
        if use_property_graph:
            graph_llm = getattr(ingestion_settings, "graph_llm_model", None)
            ingestor = LegalPropertyGraphIngestor(llm=graph_llm)
            if upsert_doc_id:
                ingestor.delete_by_doc_id(upsert_doc_id)
            ingestor.ingest_nodes(
                nodes,
                run_semantic_linking=run_semantic_linking,
                run_community_detection=run_community_detection,
                run_topic_extraction=run_topic_extraction,
                run_citation_linking=run_citation_linking,
                run_temporal_linking=run_temporal_linking,
                run_entity_cooccurrence=run_entity_cooccurrence,
            )
            return len(nodes)
        else:
            return 0

    except Exception:
        return 0


async def index_nodes(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    enable_qdrant: bool = True,
    enable_elasticsearch: bool = False,
    enable_neo4j: bool = False,
    upsert_doc_id: Optional[str] = None,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
) -> dict:
    results = {}

    if enable_qdrant:
        qdrant_store = index_nodes_to_qdrant(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["qdrant"] = qdrant_store is not None

    if enable_elasticsearch:
        es_store = await index_nodes_to_elasticsearch(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["elasticsearch"] = es_store is not None

    if enable_neo4j:
        neo4j_count = index_nodes_to_neo4j(
            nodes,
            upsert_doc_id=upsert_doc_id,
            run_semantic_linking=run_semantic_linking,
            run_community_detection=run_community_detection,
            run_topic_extraction=run_topic_extraction,
            run_citation_linking=run_citation_linking,
            run_temporal_linking=run_temporal_linking,
            run_entity_cooccurrence=run_entity_cooccurrence,
        )
        results["neo4j"] = neo4j_count > 0

    return results
