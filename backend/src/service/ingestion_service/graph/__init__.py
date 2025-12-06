"""
Graph database module for Neo4j.

Contains:
- neo4j_indexer: Main indexing functions
- property_graph_ingestor: LlamaIndex property graph ingestion
- graphrag_extractor: GraphRAG V2-style entity/relationship extraction
- entity_deduplication: Entity resolution and deduplication
- custom_retrievers: Entity-aware and global search retrievers
- linkers/: Graph enrichment linkers (community, semantic, topic, etc.)
"""

from src.service.ingestion_service.graph.entity_deduplication import (
    EntityDeduplicator,
)
from src.service.ingestion_service.graph.graphrag_extractor import (
    GraphRAGExtractor,
    create_graphrag_extractor,
)
from src.service.ingestion_service.graph.neo4j_indexer import index_nodes_to_neo4j
from src.service.ingestion_service.graph.property_graph_ingestor import (
    LegalPropertyGraphIngestor,
)

__all__ = [
    "index_nodes_to_neo4j",
    "LegalPropertyGraphIngestor",
    "GraphRAGExtractor",
    "create_graphrag_extractor",
    "EntityDeduplicator",
]
