"""Database cleanup utilities implemented with LlamaIndex stores.

These helpers clear Qdrant, Elasticsearch, and Neo4j using the same
configuration the ingestion pipeline relies on. They prefer the
LlamaIndex store clients first, and gracefully fall back to native
clients when needed so existing infrastructure keeps working.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

from llama_index.graph_stores.neo4j import Neo4jGraphStore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def clear_qdrant_collection() -> bool:
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")

        # Build client explicitly so auth-less setups work and URL is always provided.
        client_kwargs = {"url": qdrant_url}
        if api_key:
            client_kwargs["api_key"] = api_key
        qdrant_client = QdrantClient(**client_kwargs)

        store = QdrantVectorStore(
            collection_name=collection_name,
            client=qdrant_client,
        )
        client = getattr(store, "client", None) or qdrant_client
        if client is None:
            raise RuntimeError("QdrantVectorStore did not expose a client")

        logger.info("Connecting to Qdrant: %s", qdrant_url)
        collections = client.get_collections()
        exists = any(col.name == collection_name for col in collections.collections)
        if exists:
            logger.info("Deleting existing Qdrant collection: %s", collection_name)
            client.delete_collection(collection_name=collection_name)
            logger.info("Cleared Qdrant collection '%s'", collection_name)
        else:
            logger.info("Qdrant collection '%s' does not exist", collection_name)
        return True
    except KeyError as exc:
        logger.error("Missing environment variable: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.error("Error clearing Qdrant collection: %s", exc)
        return False


def clear_elasticsearch_index() -> bool:
    try:
        es_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]

        store = ElasticsearchStore(index_name=index_name, es_url=es_url)
        client = getattr(store, "client", None)
        if client is None:
            raise RuntimeError("ElasticsearchStore did not expose a client")

        logger.info("Connecting to Elasticsearch: %s", es_url)

        # Client may be async; normalize to sync calls when possible.
        exists_fn = getattr(client.indices, "exists", None)
        delete_fn = getattr(client.indices, "delete", None)
        close_fn = getattr(client, "close", None) or getattr(client, "aclose", None)

        if exists_fn is None or delete_fn is None:
            raise RuntimeError("Elasticsearch client does not expose indices.exists/delete")

        # Handle coroutine or sync functions transparently.
        def _maybe_await(result):
            if hasattr(result, "__await__"):
                import asyncio
                return asyncio.get_event_loop().run_until_complete(result)
            return result

        exists = _maybe_await(exists_fn(index=index_name))
        if exists:
            logger.info("Deleting Elasticsearch index: %s", index_name)
            _maybe_await(delete_fn(index=index_name))
            logger.info("Cleared Elasticsearch index '%s'", index_name)
        else:
            logger.info("Elasticsearch index '%s' does not exist", index_name)

        # Close client/connector if supported to avoid unclosed session warnings
        if close_fn is not None:
            try:
                _maybe_await(close_fn())
            except Exception:
                pass
        return True
    except KeyError as exc:
        logger.error("Missing environment variable: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.error("Error clearing Elasticsearch index: %s", exc)
        return False


def clear_neo4j_database() -> bool:
    try:
        uri = os.environ["NEO4J_URI"]
        username = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER")
        if not username:
            raise KeyError("NEO4J_USERNAME")
        password = os.environ["NEO4J_PASSWORD"]

        store = Neo4jGraphStore(url=uri, username=username, password=password)
        driver = getattr(store, "driver", None) or getattr(store, "_driver", None)
        if driver is None:
            raise RuntimeError("Neo4jGraphStore did not expose a driver")

        logger.info("Connecting to Neo4j: %s", uri)
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            summary = session.run("MATCH (n) RETURN count(n) as node_count").single()
            remaining = summary["node_count"] if summary else 0
        logger.info("Cleared Neo4j database; remaining nodes: %s", remaining)
        return True
    except KeyError as exc:
        logger.error("Missing environment variable: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - depends on external services
        logger.error("Error clearing Neo4j database: %s", exc)
        return False


def clear_all_databases() -> Dict[str, bool]:
    logger.info("🧹 Starting database cleanup via LlamaIndex stores...")

    results = {
        "qdrant": clear_qdrant_collection(),
        "elasticsearch": clear_elasticsearch_index(),
        "neo4j": clear_neo4j_database(),
    }

    successes = sum(result for result in results.values())
    if successes == len(results):
        logger.info("✅ Successfully cleared all databases")
    else:
        failed = [name for name, ok in results.items() if not ok]
        logger.warning("⚠️ Issues clearing: %s", ", ".join(failed))

    return results
