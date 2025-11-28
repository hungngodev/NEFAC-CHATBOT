from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import List, Optional

from llama_index.core import Settings, StorageContext
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.vector_stores.elasticsearch import (
    AsyncBM25Strategy,
    ElasticsearchStore,
)

# ... (keeping other imports)
# ... (skipping to create_elasticsearch_store)
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from src.service.ingestion_service import settings as ingestion_settings
from src.service.ingestion_service.llamaindex.metadata_utils import build_chunk_id, sanitize_metadata
from src.service.ingestion_service.llamaindex.property_graph_ingestor import LegalPropertyGraphIngestor

logger = logging.getLogger(__name__)


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
    logger.info("Creating unified storage context")

    if docstore is None:
        docstore = SimpleDocumentStore()

    primary_vector_store = qdrant_store or elasticsearch_store

    if primary_vector_store is None:
        logger.warning("No vector store provided to StorageContext")

    return StorageContext.from_defaults(
        vector_store=primary_vector_store,
        graph_store=neo4j_graph_store,
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

    client_kwargs = {"url": url}
    if api_key:
        client_kwargs["api_key"] = api_key
    client = QdrantClient(**client_kwargs)

    # Standard dense-only
    if client and not client.collection_exists(collection_name):
        from qdrant_client.http import models

        logger.info(f"Creating Qdrant collection {collection_name} (dense-only)")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=ingestion_settings.EMBEEDING_DIMENSIONS, distance=models.Distance.COSINE),
        )

    logger.info(f"Creating Qdrant store: {collection_name} (hybrid=False)")
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

    logger.info(f"Creating Elasticsearch store: {index_name} with strategy: bm25")

    try:
        return ElasticsearchStore(
            index_name=index_name,
            es_url=es_url,
            retrieval_strategy=AsyncBM25Strategy(),
        )

    except ImportError as e:
        logger.error(f"Failed to import Elasticsearch strategies: {e}")
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


def _ensure_es_index(client, index_name: str) -> bool:
    if client is None:
        return False
    try:
        exists = bool(_await_maybe(client.indices.exists(index=index_name)))
        if not exists:
            _await_maybe(client.indices.create(index=index_name, ignore=400))
        return True
    except Exception as exc:
        logger.debug("ES index existence check failed for %s: %s", index_name, exc)
        return False


def index_nodes_to_qdrant(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    collection_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
) -> Optional[QdrantVectorStore]:
    if not nodes:
        logger.warning("No nodes to index to Qdrant")
        return None

    try:
        vector_store = create_qdrant_store(collection_name=collection_name)
        embedder = embed_model or Settings.embed_model

        if embedder is None:
            logger.error("No embedding model configured; skipping Qdrant indexing")
            return None

        if upsert_doc_id:
            client = getattr(vector_store, "client", None)
            if client:
                try:
                    client.delete(
                        collection_name=vector_store.collection_name,
                        points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=upsert_doc_id))]),
                    )
                    logger.info("Deleted existing Qdrant points for doc_id=%s", upsert_doc_id)
                except Exception as exc:
                    logger.debug("Delete Qdrant points skipped for doc_id=%s: %s", upsert_doc_id, exc)

        pipeline = IngestionPipeline(
            transformations=[
                embedder,
            ],
            docstore=SimpleDocumentStore(),
            vector_store=vector_store,
        )

        cleaned_nodes = [_clean_text_node(node, include_text_field=True) for node in nodes]
        pipeline.run(nodes=cleaned_nodes)

        logger.info(f"✅ Indexed {len(cleaned_nodes)} nodes to Qdrant")
        _close_maybe_async(getattr(vector_store, "client", None))
        return vector_store

    except Exception as e:
        logger.error(f"Failed to index to Qdrant: {e}")
        return None


def index_nodes_to_elasticsearch(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    index_name: Optional[str] = None,
    upsert_doc_id: Optional[str] = None,
) -> Optional[ElasticsearchStore]:
    if not nodes:
        logger.warning("No nodes to index to Elasticsearch")
        return None

    vector_store = create_elasticsearch_store(index_name=index_name)
    # embedder = embed_model or Settings.embed_model
    # if embedder is None:
    #     logger.error("No embedding model configured; skipping Elasticsearch indexing")
    #     return None

    client = getattr(vector_store, "client", None)
    index_exists = _ensure_es_index(client, vector_store.index_name)

    if upsert_doc_id and client and index_exists:
        try:
            _await_maybe(
                client.delete_by_query(
                    index=vector_store.index_name,
                    body={"query": {"term": {"doc_id": upsert_doc_id}}},
                    ignore_unavailable=True,
                )
            )
            logger.info("Deleted existing Elasticsearch docs for doc_id=%s", upsert_doc_id)
        except Exception as exc:
            logger.debug("Delete ES docs skipped for doc_id=%s: %s", upsert_doc_id, exc)

    try:
        pipeline = IngestionPipeline(
            transformations=[],  # No embeddings for ES (BM25 only)
            docstore=SimpleDocumentStore(),
            vector_store=vector_store,
        )
        cleaned_nodes = [_clean_text_node(node, include_text_field=True) for node in nodes]
        pipeline.run(nodes=cleaned_nodes)

        logger.info(f"✅ Indexed {len(cleaned_nodes)} nodes to Elasticsearch")
        _close_maybe_async(getattr(vector_store, "client", None))
        return vector_store
    except Exception as exc:
        logger.error("Failed to index to Elasticsearch: %s", exc)
        return None


def index_nodes_to_neo4j(
    nodes: List[BaseNode],
    use_property_graph: bool = True,
    upsert_doc_id: Optional[str] = None,
) -> int:
    if not nodes:
        logger.warning("No nodes to index to Neo4j")
        return 0

    try:
        if use_property_graph:
            graph_llm = getattr(ingestion_settings, "graph_llm_model", None)
            ingestor = LegalPropertyGraphIngestor(llm=graph_llm)
            if upsert_doc_id:
                ingestor.delete_by_doc_id(upsert_doc_id)
            ingestor.ingest_nodes(nodes)
            return len(nodes)
        else:
            logger.warning("Basic graph indexing not implemented, use property_graph=True")
            return 0

    except Exception as e:
        logger.error(f"Failed to index to Neo4j: {e}")
        return 0


def index_nodes(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    enable_qdrant: bool = True,
    enable_elasticsearch: bool = False,
    enable_neo4j: bool = False,
    upsert_doc_id: Optional[str] = None,
) -> dict:
    results = {}

    if enable_qdrant:
        qdrant_store = index_nodes_to_qdrant(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["qdrant"] = qdrant_store is not None

    if enable_elasticsearch:
        es_store = index_nodes_to_elasticsearch(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["elasticsearch"] = es_store is not None

    if enable_neo4j:
        neo4j_count = index_nodes_to_neo4j(nodes, upsert_doc_id=upsert_doc_id)
        results["neo4j"] = neo4j_count > 0

    return results
