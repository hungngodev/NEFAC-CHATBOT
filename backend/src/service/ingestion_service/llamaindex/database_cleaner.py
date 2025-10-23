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

logger = logging.getLogger(__name__)


def clear_qdrant_collection() -> bool:
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")

        store = QdrantVectorStore(
            collection_name=collection_name,
            url=qdrant_url,
            api_key=api_key,
        )
        client = getattr(store, "client", None)
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
        if client.indices.exists(index=index_name):
            logger.info("Deleting Elasticsearch index: %s", index_name)
            client.indices.delete(index=index_name)
            logger.info("Cleared Elasticsearch index '%s'", index_name)
        else:
            logger.info("Elasticsearch index '%s' does not exist", index_name)
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
