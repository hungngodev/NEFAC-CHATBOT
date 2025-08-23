"""
Database cleaner service to clear all existing data from Qdrant, Elasticsearch, and Neo4j.
"""

import logging
import os

from elasticsearch import Elasticsearch
from langchain_neo4j import Neo4jGraph
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def clear_qdrant_collection() -> bool:
    """Clear all data from the Qdrant collection."""
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")  # Will be None for local

        # Initialize Qdrant client
        if api_key:
            client = QdrantClient(url=qdrant_url, api_key=api_key)
        else:
            # Local Qdrant doesn't need API key
            client = QdrantClient(url=qdrant_url)

        # Check if collection exists
        try:
            collections = client.get_collections()
            collection_exists = any(col.name == collection_name for col in collections.collections)

            if collection_exists:
                logger.info(f"Deleting existing Qdrant collection: {collection_name}")
                client.delete_collection(collection_name=collection_name)
                logger.info(f"✓ Cleared Qdrant collection '{collection_name}'")
            else:
                logger.info(f"Qdrant collection '{collection_name}' does not exist, nothing to clear")

            return True

        except Exception as e:
            logger.error(f"Error clearing Qdrant collection: {e}")
            return False

    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
        return False


def clear_elasticsearch_index() -> bool:
    """Clear all data from the Elasticsearch index."""
    try:
        elasticsearch_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]

        # Initialize Elasticsearch client
        es = Elasticsearch(elasticsearch_url)

        # Check if index exists and delete it
        if es.indices.exists(index=index_name):
            logger.info(f"Deleting existing Elasticsearch index: {index_name}")
            es.indices.delete(index=index_name)
            logger.info(f"✓ Cleared Elasticsearch index '{index_name}'")
        else:
            logger.info(f"Elasticsearch index '{index_name}' does not exist, nothing to clear")

        return True

    except Exception as e:
        logger.error(f"Error clearing Elasticsearch index: {e}")
        return False


def clear_neo4j_database() -> bool:
    """Clear all data from the Neo4j database."""
    try:
        neo4j_uri = os.environ["NEO4J_URI"]
        neo4j_user = os.environ["NEO4J_USER"]
        neo4j_password = os.environ["NEO4J_PASSWORD"]

        # Initialize Neo4j graph
        graph = Neo4jGraph(url=neo4j_uri, username=neo4j_user, password=neo4j_password)

        logger.info("Clearing all data from Neo4j database...")

        # Delete all nodes and relationships
        clear_query = """
        MATCH (n)
        DETACH DELETE n
        """
        graph.query(clear_query)

        # Verify the database is empty
        count_query = "MATCH (n) RETURN count(n) as node_count"
        result = graph.query(count_query)
        node_count = result[0]["node_count"] if result else 0

        logger.info(f"✓ Cleared Neo4j database. Remaining nodes: {node_count}")
        return True

    except Exception as e:
        logger.error(f"Error clearing Neo4j database: {e}")
        return False


def clear_all_databases() -> dict[str, bool]:
    """
    Clear all databases (Qdrant, Elasticsearch, Neo4j).
    Returns a dictionary with the success status for each database.
    """
    logger.info("🧹 Starting database cleanup...")

    results = {"qdrant": clear_qdrant_collection(), "elasticsearch": clear_elasticsearch_index(), "neo4j": clear_neo4j_database()}

    success_count = sum(results.values())
    total_count = len(results)

    if success_count == total_count:
        logger.info(f"✅ Successfully cleared all {total_count} databases")
    else:
        failed_dbs = [db for db, success in results.items() if not success]
        logger.warning(f"⚠️  Successfully cleared {success_count}/{total_count} databases. Failed: {', '.join(failed_dbs)}")

    return results
