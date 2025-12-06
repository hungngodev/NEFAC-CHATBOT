"""
Neo4j graph database indexer.

Handles indexing documents to Neo4j property graph for knowledge graph operations.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from llama_index.core.schema import BaseNode

from src.service.ingestion_service import settings as ingestion_settings

logger = logging.getLogger(__name__)


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
    use_strict_schema: bool = True,
    use_graphrag_descriptions: bool = False,
) -> int:
    """
    Index nodes to Neo4j property graph.

    Args:
        nodes: List of nodes to index
        use_property_graph: Use property graph mode (default True)
        upsert_doc_id: If provided, delete existing docs with this ID first
        run_semantic_linking: Run semantic similarity linking
        run_community_detection: Run community detection
        run_topic_extraction: Extract topics from documents
        run_citation_linking: Link legal citations
        run_temporal_linking: Link temporal references
        run_entity_cooccurrence: Link co-occurring entities
        use_strict_schema: Use SchemaLLMPathExtractor with Pydantic validation
        use_graphrag_descriptions: Add entity/relationship descriptions

    Returns:
        Number of nodes indexed
    """
    if not nodes:
        logger.warning("No nodes to index to Neo4j")
        return 0

    try:
        if use_property_graph:
            # Import here to avoid circular imports
            from src.service.ingestion_service.graph.property_graph_ingestor import (
                LegalPropertyGraphIngestor,
            )

            graph_llm = getattr(ingestion_settings, "graph_llm_model", None)
            ingestor = LegalPropertyGraphIngestor(
                llm=graph_llm,
                use_strict_schema=use_strict_schema,
                use_graphrag_descriptions=use_graphrag_descriptions,
            )

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
            logger.warning("Basic graph indexing not implemented, use property_graph=True")
            return 0

    except Exception as e:
        logger.error(f"Failed to index to Neo4j: {e}")
        return 0
