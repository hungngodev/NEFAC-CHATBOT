from __future__ import annotations

import asyncio
import os
from typing import Any, Dict

from llama_index.graph_stores.neo4j import Neo4jGraphStore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore
from qdrant_client import QdrantClient


def _maybe_await(result):
    if hasattr(result, "__await__"):
        return asyncio.get_event_loop().run_until_complete(result)
    return result


def clear_qdrant_collection() -> bool:
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")

        client_kwargs: Dict[str, Any] = {"url": qdrant_url}
        if api_key:
            client_kwargs["api_key"] = api_key
        client = QdrantClient(**client_kwargs)

        if client.collection_exists(collection_name):
            client.delete_collection(collection_name=collection_name)
        return True
    except KeyError:
        return False


def clear_elasticsearch_index() -> bool:
    try:
        es_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]

        store = ElasticsearchStore(index_name=index_name, es_url=es_url)
        client = getattr(store, "client", None)
        if client is None:
            return False

        if _maybe_await(client.indices.exists(index=index_name)):
            _maybe_await(client.indices.delete(index=index_name))

        close_fn = getattr(client, "close", None) or getattr(client, "aclose", None)
        if close_fn:
            try:
                _maybe_await(close_fn())
            except Exception:
                pass
        return True
    except KeyError:
        return False


def clear_neo4j_database() -> bool:
    try:
        uri = os.environ["NEO4J_URI"]
        username = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER")
        if not username:
            return False
        password = os.environ["NEO4J_PASSWORD"]

        store = Neo4jGraphStore(url=uri, username=username, password=password)
        driver = getattr(store, "driver", None) or getattr(store, "_driver", None)
        if driver is None:
            return False

        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        return True
    except KeyError:
        return False


def clear_all_databases(
    clear_qdrant: bool = True,
    clear_elasticsearch: bool = True,
    clear_neo4j: bool = True,
) -> Dict[str, bool]:
    results = {}
    if clear_qdrant:
        results["qdrant"] = clear_qdrant_collection()
    if clear_elasticsearch:
        results["elasticsearch"] = clear_elasticsearch_index()
    if clear_neo4j:
        results["neo4j"] = clear_neo4j_database()
    return results
