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
    if not nodes:
        return 0

    if not use_property_graph:
        return 0

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
