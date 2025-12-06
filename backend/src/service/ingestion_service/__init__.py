"""
Ingestion Service Package

Organized by database type:
- vector/     - Qdrant vector database indexing
- keyword/    - Elasticsearch keyword search indexing
- graph/      - Neo4j property graph indexing
- shared/     - Common utilities
- loader/     - Document loading
- orchestration/ - Workflow coordination
- llamaindex/ - Legacy location (being migrated)

Import from specific submodules for production use.
"""

# Note: Keep imports minimal to avoid import errors when optional
# dependencies are not installed. Import directly from submodules:
#
# from src.service.ingestion_service.vector import create_qdrant_store
# from src.service.ingestion_service.keyword import create_elasticsearch_store
# from src.service.ingestion_service.graph import LegalPropertyGraphIngestor
# from src.service.ingestion_service.orchestration import index_nodes
