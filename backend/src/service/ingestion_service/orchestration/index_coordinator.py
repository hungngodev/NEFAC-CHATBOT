"""
Index coordinator for multi-database ingestion.

Orchestrates ingestion across vector (Qdrant), keyword (Elasticsearch), 
and graph (Neo4j) databases.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from llama_index.core.schema import BaseNode

from src.service.ingestion_service.graph.neo4j_indexer import index_nodes_to_neo4j
from src.service.ingestion_service.keyword.elasticsearch_indexer import (
    index_nodes_to_elasticsearch,
)
from src.service.ingestion_service.vector.qdrant_indexer import index_nodes_to_qdrant

logger = logging.getLogger(__name__)


async def index_nodes(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    enable_qdrant: bool = True,
    enable_elasticsearch: bool = False,
    enable_neo4j: bool = False,
    upsert_doc_id: Optional[str] = None,
    # Neo4j specific options
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    use_strict_schema: bool = True,
    use_graphrag_descriptions: bool = False,
) -> dict:
    """
    Index nodes to multiple databases.

    This is the main entry point for multi-database ingestion. It coordinates
    indexing across vector, keyword, and graph databases based on configuration.

    Args:
        nodes: List of nodes to index
        embed_model: Embedding model for vector indexing
        enable_qdrant: Enable Qdrant vector indexing
        enable_elasticsearch: Enable Elasticsearch keyword indexing
        enable_neo4j: Enable Neo4j graph indexing
        upsert_doc_id: If provided, delete existing docs with this ID first
        run_semantic_linking: Run semantic similarity linking (Neo4j)
        run_community_detection: Run community detection (Neo4j)
        run_topic_extraction: Extract topics (Neo4j)
        run_citation_linking: Link legal citations (Neo4j)
        run_temporal_linking: Link temporal references (Neo4j)
        run_entity_cooccurrence: Link co-occurring entities (Neo4j)
        use_strict_schema: Use strict schema validation (Neo4j)
        use_graphrag_descriptions: Add entity/relationship descriptions (Neo4j)

    Returns:
        Dictionary with success status for each database
    """
    results = {}

    if enable_qdrant:
        logger.info("Indexing to Qdrant...")
        qdrant_store = index_nodes_to_qdrant(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["qdrant"] = qdrant_store is not None

    if enable_elasticsearch:
        logger.info("Indexing to Elasticsearch...")
        es_store = await index_nodes_to_elasticsearch(nodes, embed_model, upsert_doc_id=upsert_doc_id)
        results["elasticsearch"] = es_store is not None

    if enable_neo4j:
        logger.info("Indexing to Neo4j...")
        neo4j_count = index_nodes_to_neo4j(
            nodes,
            upsert_doc_id=upsert_doc_id,
            run_semantic_linking=run_semantic_linking,
            run_community_detection=run_community_detection,
            run_topic_extraction=run_topic_extraction,
            run_citation_linking=run_citation_linking,
            run_temporal_linking=run_temporal_linking,
            run_entity_cooccurrence=run_entity_cooccurrence,
            use_strict_schema=use_strict_schema,
            use_graphrag_descriptions=use_graphrag_descriptions,
        )
        results["neo4j"] = neo4j_count > 0

    return results
