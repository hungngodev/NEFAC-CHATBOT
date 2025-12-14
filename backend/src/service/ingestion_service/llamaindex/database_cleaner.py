from __future__ import annotations

import os
from typing import Any, Dict

from llama_index.graph_stores.neo4j import Neo4jGraphStore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def clear_qdrant_collection() -> bool:
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")

        client_kwargs: Dict[str, Any] = {"url": qdrant_url}
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

        collections = client.get_collections()
        exists = any(col.name == collection_name for col in collections.collections)
        if exists:
            client.delete_collection(collection_name=collection_name)
        else:
            pass
        return True
    except KeyError:
        return False
    except Exception:
        return False


def clear_elasticsearch_index() -> bool:
    try:
        es_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]

        store = ElasticsearchStore(index_name=index_name, es_url=es_url)
        client = getattr(store, "client", None)
        if client is None:
            raise RuntimeError("ElasticsearchStore did not expose a client")

        exists_fn = getattr(client.indices, "exists", None)
        delete_fn = getattr(client.indices, "delete", None)
        close_fn = getattr(client, "close", None) or getattr(client, "aclose", None)

        if exists_fn is None or delete_fn is None:
            raise RuntimeError("Elasticsearch client does not expose indices.exists/delete")

        def _maybe_await(result):
            if hasattr(result, "__await__"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(result)
            return result

        exists = _maybe_await(exists_fn(index=index_name))
        if exists:
            _maybe_await(delete_fn(index=index_name))
        else:

            pass
        if close_fn is not None:
            try:
                _maybe_await(close_fn())
            except Exception:
                pass
        return True
    except KeyError:
        return False
    except Exception:
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

        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            summary = session.run("MATCH (n) RETURN count(n) as node_count").single()
            summary["node_count"] if summary else 0
        return True
    except KeyError:
        return False
    except Exception:
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

    successes = sum(result for result in results.values())
    if successes == len(results):
        pass
    else:
        [name for name, ok in results.items() if not ok]

    return results
