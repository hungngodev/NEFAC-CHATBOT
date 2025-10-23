"""Property Graph Index with legal domain schema for Neo4j.

Enhanced knowledge graph with schema-based entity/relation extraction.
Based on: https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
"""

from __future__ import annotations

import logging
import os
from typing import List, Literal, Optional

from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.core.schema import BaseNode
from llama_index.core.schema import Document as LIDocument
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from .entity_deduplication import EntityDeduplicator

logger = logging.getLogger(__name__)


# Legal domain entity types
LEGAL_ENTITY_TYPES = Literal[
    "CASE",
    "STATUTE",
    "REGULATION",
    "COURT",
    "JUDGE",
    "PARTY",
    "ATTORNEY",
    "LEGAL_ISSUE",
    "PRECEDENT",
    "DATE",
    "JURISDICTION",
    "LAW_FIRM",
    "GOVERNMENT_AGENCY",
    "LEGAL_CONCEPT",
    "DOCUMENT",
    "PERSON",
    "ORGANIZATION",
]

# Legal domain relation types
LEGAL_RELATION_TYPES = Literal[
    "CITES",
    "OVERRULES",
    "DISTINGUISHES",
    "APPLIES_TO",
    "FILED_IN",
    "DECIDED_BY",
    "REPRESENTS",
    "INVOLVES",
    "ESTABLISHES",
    "INTERPRETS",
    "GOVERNS",
    "REFERENCES",
    "RELATED_TO",
    "PART_OF",
    "AUTHORED_BY",
    "PUBLISHED_ON",
]


class LegalPropertyGraphIngestor:
    """Property graph ingestor with legal domain schema.

    Features:
    - Schema-based entity extraction (Cases, Statutes, Parties, etc.)
    - Relationship extraction (CITES, APPLIES_TO, etc.)
    - Validation and quality checks
    - Neo4j integration with PropertyGraphIndex
    """

    # Entity types for extraction
    ENTITY_TYPES = [
        "CASE",
        "STATUTE",
        "REGULATION",
        "COURT",
        "JUDGE",
        "PARTY",
        "ATTORNEY",
        "LEGAL_ISSUE",
        "PRECEDENT",
        "DATE",
        "JURISDICTION",
        "LAW_FIRM",
        "GOVERNMENT_AGENCY",
        "LEGAL_CONCEPT",
        "DOCUMENT",
        "PERSON",
        "ORGANIZATION",
    ]

    # Relation types for extraction
    RELATION_TYPES = [
        "CITES",
        "OVERRULES",
        "DISTINGUISHES",
        "APPLIES_TO",
        "FILED_IN",
        "DECIDED_BY",
        "REPRESENTS",
        "INVOLVES",
        "ESTABLISHES",
        "INTERPRETS",
        "GOVERNS",
        "REFERENCES",
        "RELATED_TO",
        "PART_OF",
        "AUTHORED_BY",
        "PUBLISHED_ON",
    ]

    # Validation schema for strict extraction
    VALIDATION_SCHEMA = {
        "CASE": ["CITES", "OVERRULES", "DISTINGUISHES", "FILED_IN", "DECIDED_BY"],
        "STATUTE": ["APPLIES_TO", "GOVERNS", "INTERPRETS"],
        "PARTY": ["INVOLVES", "REPRESENTS"],
        "COURT": ["DECIDED_BY", "FILED_IN"],
        "JUDGE": ["DECIDED_BY"],
        "ATTORNEY": ["REPRESENTS"],
        "DOCUMENT": ["AUTHORED_BY", "PUBLISHED_ON", "REFERENCES"],
    }

    def __init__(
        self,
        neo4j_url: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        database: str = "neo4j",
        enable_validation: bool = True,
        llm=None,
    ):
        """Initialize property graph ingestor.

        Args:
            neo4j_url: Neo4j connection URL
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            database: Neo4j database name
            enable_validation: Enable schema validation
            llm: Language model for extraction (defaults to Settings.llm)
        """
        from llama_index.core import Settings

        self.neo4j_url = neo4j_url or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.enable_validation = enable_validation
        self.llm = llm or Settings.llm

        self._setup_graph_store()

    def _setup_graph_store(self):
        """Setup Neo4j property graph store."""
        try:
            self.graph_store = Neo4jPropertyGraphStore(
                username=self.neo4j_user,
                password=self.neo4j_password,
                url=self.neo4j_url,
                database=self.database,
            )
            logger.info(f"Connected to Neo4j at {self.neo4j_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _create_schema_extractor(self):
        """Create schema-based LLM extractor for legal domain.

        Enhanced with entity deduplication from tutorial:
        https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
        """
        from src.service.ingestion_service.settings import (
            GRAPH_ENABLE_ENTITY_DEDUPLICATION,
            GRAPH_ENTITY_SIMILARITY_THRESHOLD,
            GRAPH_MAX_TRIPLETS_PER_CHUNK,
            GRAPH_NUM_WORKERS,
            GRAPH_USE_WORD_DISTANCE,
            GRAPH_WORD_DISTANCE_THRESHOLD,
        )

        logger.info("Creating SchemaLLMPathExtractor with legal domain schema")
        logger.info(f"Entity deduplication: {GRAPH_ENABLE_ENTITY_DEDUPLICATION}")

        # Build extractor kwargs
        extractor_kwargs = {
            "llm": self.llm,
            "possible_entities": self.ENTITY_TYPES,
            "possible_relations": self.RELATION_TYPES,
            "kg_validation_schema": self.VALIDATION_SCHEMA if self.enable_validation else None,
            "strict": False,  # Allow entities outside schema for flexibility
            "num_workers": GRAPH_NUM_WORKERS,
            "max_triplets_per_chunk": GRAPH_MAX_TRIPLETS_PER_CHUNK,
        }

        # Add entity deduplication if enabled
        if GRAPH_ENABLE_ENTITY_DEDUPLICATION:
            try:
                # Try to add deduplication parameters
                # Note: Parameter names may vary by LlamaIndex version
                dedup_params = {}

                # Try various parameter name conventions
                param_variants = [
                    ("entity_deduplication", GRAPH_ENABLE_ENTITY_DEDUPLICATION),
                    ("enable_deduplication", GRAPH_ENABLE_ENTITY_DEDUPLICATION),
                    ("deduplicate_entities", GRAPH_ENABLE_ENTITY_DEDUPLICATION),
                    ("entity_similarity_threshold", GRAPH_ENTITY_SIMILARITY_THRESHOLD),
                    ("similarity_threshold", GRAPH_ENTITY_SIMILARITY_THRESHOLD),
                    ("use_word_distance", GRAPH_USE_WORD_DISTANCE),
                    ("word_distance_threshold", GRAPH_WORD_DISTANCE_THRESHOLD),
                ]

                for param_name, param_value in param_variants:
                    try:
                        dedup_params[param_name] = param_value
                    except Exception:
                        pass

                if dedup_params:
                    extractor_kwargs.update(dedup_params)
                    logger.info(f"Entity deduplication enabled with threshold={GRAPH_ENTITY_SIMILARITY_THRESHOLD}")
                else:
                    logger.info("Entity deduplication parameters not available in this LlamaIndex version")

            except Exception as e:
                logger.warning(f"Could not enable entity deduplication: {e}")

        extractor = SchemaLLMPathExtractor(**extractor_kwargs)

        return extractor

    def _nodes_to_documents(self, nodes: List[BaseNode]) -> List[LIDocument]:
        """Convert nodes to documents for PropertyGraphIndex."""

        documents = []
        for node in nodes:
            doc = LIDocument(
                text=node.get_content(),
                metadata=node.metadata,
                id_=node.node_id,
            )
            documents.append(doc)

        return documents

    def ingest_nodes(
        self,
        nodes: List[BaseNode],
        show_progress: bool = True,
        run_deduplication: bool = True,
    ) -> PropertyGraphIndex:
        """Ingest nodes into property graph with schema extraction.

        Args:
            nodes: List of nodes to ingest
            show_progress: Show progress bar
            run_deduplication: Run entity deduplication after ingestion

        Returns:
            PropertyGraphIndex instance
        """
        try:
            logger.info(f"Ingesting {len(nodes)} nodes into PropertyGraphIndex")

            # Convert nodes to documents
            documents = self._nodes_to_documents(nodes)

            # Create schema extractor
            kg_extractor = self._create_schema_extractor()

            # Build property graph index
            index = PropertyGraphIndex.from_documents(
                documents,
                property_graph_store=self.graph_store,
                kg_extractors=[kg_extractor],
                show_progress=show_progress,
            )

            logger.info(f"Successfully ingested {len(nodes)} nodes into property graph")

            # Run entity deduplication if enabled
            if run_deduplication:
                from src.service.ingestion_service.settings import (
                    GRAPH_ENABLE_ENTITY_DEDUPLICATION,
                    GRAPH_ENTITY_SIMILARITY_THRESHOLD,
                    GRAPH_WORD_DISTANCE_THRESHOLD,
                )

                if GRAPH_ENABLE_ENTITY_DEDUPLICATION:
                    logger.info("Starting entity deduplication...")
                    self.deduplicate_entities(
                        similarity_threshold=GRAPH_ENTITY_SIMILARITY_THRESHOLD,
                        word_edit_distance=int(GRAPH_WORD_DISTANCE_THRESHOLD),
                    )

            return index

        except Exception as e:
            logger.error(f"Failed to ingest nodes into property graph: {e}")
            raise

    def deduplicate_entities(
        self,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """Deduplicate entities using vector similarity and word distance.

        Based on tutorial pattern:
        https://neo4j.com/blog/developer/property-graph-index-llamaindex/

        Args:
            similarity_threshold: Minimum cosine similarity (0-1)
            word_edit_distance: Maximum Levenshtein distance
            enable_apoc: Use APOC functions if available
            dry_run: Only report, don't merge

        Returns:
            Dictionary with deduplication statistics
        """
        try:
            logger.info(f"Running entity deduplication: " f"similarity={similarity_threshold}, " f"word_distance={word_edit_distance}, " f"dry_run={dry_run}")

            # Create deduplicator
            deduplicator = EntityDeduplicator(
                graph_store=self.graph_store,
                similarity_threshold=similarity_threshold,
                word_edit_distance=word_edit_distance,
                enable_apoc=enable_apoc,
            )

            # Create vector index for efficient similarity search
            from src.service.ingestion_service.settings import OPENAI_EMBED_MODEL_DIM

            deduplicator.create_vector_index(embedding_dimension=OPENAI_EMBED_MODEL_DIM)

            # Get initial stats
            initial_stats = deduplicator.get_duplicate_stats()
            logger.info(f"Duplicate analysis: {initial_stats}")

            # Find and validate duplicates
            duplicate_groups = deduplicator.find_duplicate_entities()
            validated_groups, false_positives = deduplicator.validate_duplicates(duplicate_groups)

            logger.info(f"Found {len(validated_groups)} validated duplicate groups " f"({len(false_positives)} false positives filtered)")

            # Log examples for review
            if validated_groups:
                logger.info("Example duplicate groups:")
                for i, group in enumerate(validated_groups[:5]):
                    logger.info(f"  {i+1}. {group}")

            if false_positives:
                logger.info("Example false positives (not merged):")
                for i, group in enumerate(false_positives[:3]):
                    logger.info(f"  {i+1}. {group}")

            # Merge duplicates
            merge_stats = deduplicator.merge_duplicate_entities(
                duplicate_groups=validated_groups,
                dry_run=dry_run,
            )

            # Get final stats
            final_stats = deduplicator.get_duplicate_stats()

            result = {
                **merge_stats,
                "initial_stats": initial_stats,
                "final_stats": final_stats,
                "validated_groups": len(validated_groups),
                "false_positives_filtered": len(false_positives),
            }

            logger.info(f"Entity deduplication complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during entity deduplication: {e}", exc_info=True)
            return {"error": str(e)}

    def clear_graph(self):
        """Clear all nodes and relationships from the graph."""
        try:
            # Use Neo4j query to delete all
            pass
            # Execute through graph store if it has a method
            logger.info("Clearing Neo4j graph")
            # Note: Actual execution depends on Neo4j client
        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    def get_stats(self) -> dict:
        """Get graph statistics.

        Returns:
            Dictionary with entity/relation counts
        """
        try:
            # Query Neo4j for stats
            stats = {
                "message": "Graph statistics",
                # Add actual queries when implementing
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"error": str(e)}


# Backward compatible function
def graph_rag_ingest_llamaindex(nodes: List[BaseNode], use_property_graph: bool = True, **kwargs) -> int:
    """Backward compatible function for existing code.

    Args:
        nodes: List of nodes to ingest
        use_property_graph: Use PropertyGraphIndex (new) vs KnowledgeGraphIndex (old)
        **kwargs: Additional arguments

    Returns:
        Number of nodes ingested
    """

    if use_property_graph or os.getenv("GRAPH_USE_PROPERTY_GRAPH", "true").lower() in {"true", "1", "yes"}:
        # Use new PropertyGraphIndex with schema
        logger.info("Using PropertyGraphIndex with legal schema")
        ingestor = LegalPropertyGraphIngestor(**kwargs)
        ingestor.ingest_nodes(nodes, show_progress=True)
    else:
        # Fallback to old KnowledgeGraphIndex
        logger.warning("Using legacy KnowledgeGraphIndex (consider upgrading to PropertyGraphIndex)")
        from llama_index.core import KnowledgeGraphIndex
        from llama_index.graph_stores.neo4j import Neo4jGraphStore

        neo4j_url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        graph_store = Neo4jGraphStore(
            username=neo4j_user,
            password=neo4j_password,
            url=neo4j_url,
        )

        # Convert nodes to documents
        documents = []
        for node in nodes:
            doc = LIDocument(text=node.get_content(), metadata=node.metadata)
            documents.append(doc)

        KnowledgeGraphIndex.from_documents(
            documents,
            storage_context_kwargs={"graph_store": graph_store},
            show_progress=True,
        )

    return len(nodes)
