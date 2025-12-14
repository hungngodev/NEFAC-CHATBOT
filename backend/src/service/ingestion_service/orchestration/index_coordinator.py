from __future__ import annotations

from typing import List, Optional

from llama_index.core.schema import BaseNode

from src.service.ingestion_service.graph.neo4j_indexer import index_nodes_to_neo4j
from src.service.ingestion_service.keyword.elasticsearch_indexer import (
    index_nodes_to_elasticsearch,
)
from src.service.ingestion_service.vector.qdrant_indexer import index_nodes_to_qdrant


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
    use_strict_schema: bool = True,
    use_graphrag_descriptions: bool = False,
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
            use_strict_schema=use_strict_schema,
            use_graphrag_descriptions=use_graphrag_descriptions,
        )
        results["neo4j"] = neo4j_count > 0

    return results
