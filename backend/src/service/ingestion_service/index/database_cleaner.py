"""
Database cleaner service to clear all existing data from Qdrant, Elasticsearch, and Neo4j.
"""

import logging
import os
from typing import Dict

from elasticsearch import Elasticsearch
from langchain_neo4j import Neo4jGraph
from qdrant_client import QdrantClient

# Use colored logging
logger = logging.getLogger(__name__)


def clear_qdrant_collection() -> bool:
    """Clear all data from the Qdrant collection."""
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")  # Will be None for local

        logger.info(f"Connecting to Qdrant: {qdrant_url}")

        # Initialize Qdrant client
        try:
            if api_key:
                client = QdrantClient(url=qdrant_url, api_key=api_key)
            else:
                # Local Qdrant doesn't need API key
                client = QdrantClient(url=qdrant_url)

            # Test connection
            client.get_collections()
            logger.info("✓ Qdrant connection successful")

        except Exception as conn_error:
            logger.error(f"Failed to connect to Qdrant: {conn_error}")
            return False

        # Check if collection exists
        try:
            logger.info(f"Checking Qdrant collection: {collection_name}")
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

    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        return False
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
        return False


def clear_elasticsearch_index() -> bool:
    """Clear all data from the Elasticsearch index."""
    try:
        elasticsearch_url = os.environ["ES_HOST"]
        index_name = os.environ["ES_INDEX"]

        # Initialize Elasticsearch client with version compatibility
        logger.info(f"Connecting to Elasticsearch: {elasticsearch_url}")
        es = Elasticsearch(
            elasticsearch_url,
        )

        # Test connection first
        try:
            es.info()
            logger.info("✓ Elasticsearch connection successful")
        except Exception as conn_error:
            logger.error(f"Failed to connect to Elasticsearch: {conn_error}")
            return False

        # Check if index exists and delete it
        try:
            if es.indices.exists(index=index_name):
                logger.info(f"Deleting existing Elasticsearch index: {index_name}")
                es.indices.delete(index=index_name)
                logger.info(f"✓ Cleared Elasticsearch index '{index_name}'")
            else:
                logger.info(f"Elasticsearch index '{index_name}' does not exist, nothing to clear")
            return True
        except Exception as index_error:
            logger.error(f"Error with Elasticsearch index operations: {index_error}")
            return False

    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        return False
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
        logger.info(f"Connecting to Neo4j: {neo4j_uri}")

        try:
            graph = Neo4jGraph(url=neo4j_uri, username=neo4j_user, password=neo4j_password)

            # Test connection with a simple query
            graph.query("RETURN 1 as test")
            logger.info("✓ Neo4j connection successful")

        except Exception as conn_error:
            logger.error("Could not connect to Neo4j database. Please ensure that the url is correct")
            logger.error(f"Connection details: {conn_error}")
            return False

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

    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        return False
    except Exception as e:
        logger.error(f"Error clearing Neo4j database: {e}")
        return False


def clear_all_databases() -> Dict[str, bool]:
    """
    Clear all databases (Qdrant, Elasticsearch, Neo4j).
    Returns a dictionary with the success status for each database.
    """
    logger.info("🧹 Starting database cleanup...")

    databases = ["qdrant", "elasticsearch", "neo4j"]
    results = {}

    for db_name in databases:
        logger.info(f"Clearing {db_name}...")

        if db_name == "qdrant":
            results[db_name] = clear_qdrant_collection()
        elif db_name == "elasticsearch":
            results[db_name] = clear_elasticsearch_index()
        elif db_name == "neo4j":
            results[db_name] = clear_neo4j_database()

    success_count = sum(results.values())
    total_count = len(results)

    if success_count == total_count:
        logger.info(f"✅ Successfully cleared all {total_count} databases")
    else:
        failed_dbs = [db for db, success in results.items() if not success]
        logger.warning(f"⚠️  Successfully cleared {success_count}/{total_count} databases. Failed: {', '.join(failed_dbs)}")

    return results
