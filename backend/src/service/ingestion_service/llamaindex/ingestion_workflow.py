"""LlamaIndex Workflow for durable ingestion pipeline.

Based on: https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from llama_index.core.schema import BaseNode
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

from src.service.ingestion_service.loader.unstructured_loader import load_document_nodes
from src.service.ingestion_service.settings import GRAPH_MODE, WORKFLOW_ENABLE_VALIDATION
from src.service.ingestion_service.llamaindex.indexer import (
    index_nodes_to_elasticsearch,
    index_nodes_to_neo4j,
    index_nodes_to_qdrant,
)
from src.service.ingestion_service.progress_tracker import get_tracker
logger = logging.getLogger(__name__)


# Custom Events for workflow steps
class NodesCreatedEvent(Event):
    """Event emitted when nodes are created from documents."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class ParsedNodesEvent(Event):
    """Event emitted after parse step (pass-through here)."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class ValidatedNodesEvent(Event):
    """Event emitted after validation to avoid re-processing loops."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class QdrantIndexedEvent(Event):
    """Event emitted after Qdrant indexing (or skip)."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class ElasticsearchIndexedEvent(Event):
    """Event emitted after Elasticsearch indexing (or skip)."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class Neo4jIndexedEvent(Event):
    """Event emitted after Neo4j indexing (or skip)."""

    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class IngestionWorkflow(Workflow):
    """Durable ingestion workflow with state management.

    Workflow Steps:
    1. Load documents from file
    2. Parse into nodes with contextual summaries
    3. Index in Qdrant (vector store)
    4. Index in Elasticsearch (hybrid search)
    5. Index in Neo4j (knowledge graph)

    Features:
    - Durable state management
    - Error recovery at each step
    - Progress tracking
    - Parallel indexing (where possible)
    """

    def __init__(
        self,
        enable_qdrant: bool = True,
        enable_elasticsearch: bool = True,
        enable_neo4j: bool = True,
        timeout: int = 3600,
        return_nodes: bool = False,
        **kwargs,
    ):
        """Initialize ingestion workflow.

        Args:
            enable_qdrant: Enable Qdrant vector indexing
            enable_elasticsearch: Enable Elasticsearch hybrid indexing
            enable_neo4j: Enable Neo4j knowledge graph
            timeout: Workflow timeout in seconds
            return_nodes: Include parsed nodes in the final StopEvent payload
        """
        super().__init__(timeout=timeout, **kwargs)

        self.enable_qdrant = enable_qdrant
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_neo4j = enable_neo4j
        self.return_nodes = return_nodes

        # Lazy init components (only when needed)
        self._qdrant_indexer = None
        self._es_indexer = None
        self._graph_ingestor = None

    @property
    def qdrant_indexer(self):
        """Lazy load Qdrant indexer."""
        if self._qdrant_indexer is None and self.enable_qdrant:
            try:
                self._qdrant_indexer = index_nodes_to_qdrant
            except ImportError as e:
                logger.warning(f"Qdrant indexer not available: {e}")
        return self._qdrant_indexer

    @property
    def es_indexer(self):
        """Lazy load Elasticsearch indexer."""
        if self._es_indexer is None and self.enable_elasticsearch:
            try:
                self._es_indexer = index_nodes_to_elasticsearch
            except ImportError as e:
                logger.warning(f"Elasticsearch indexer not available: {e}")
        return self._es_indexer

    @property
    def graph_ingestor(self):
        """Lazy load graph ingestor."""
        if self._graph_ingestor is None and self.enable_neo4j:
            try:
                self._graph_ingestor = index_nodes_to_neo4j
            except ImportError as e:
                logger.warning(f"Graph ingestor not available: {e}")
        return self._graph_ingestor

    @step
    async def load_documents(self, ctx: Context, ev: StartEvent) -> NodesCreatedEvent | StopEvent:
        """Step 1: Load documents using the enhanced unstructured loader."""

        file_path = ev.get("file_path")
        metadata = ev.get("metadata", {})

        if not file_path:
            return StopEvent(result={"success": False, "error": "No file_path provided"})

        logger.info(f"[Workflow] Loading document via unstructured loader: {file_path}")

        try:
            nodes, total_chunks, _ = load_document_nodes(file_path, metadata)
        except Exception as exc:
            logger.error(f"[Workflow] Failed to load document %s: %s", file_path, exc)
            return StopEvent(result={"success": False, "error": str(exc)})

        if not nodes:
            return StopEvent(result={"success": False, "error": "Loader returned no nodes"})

        logger.info("[Workflow] Loader produced %d nodes", len(nodes))

        return NodesCreatedEvent(nodes=nodes, file_path=file_path, metadata=metadata)

    @step
    async def parse_nodes(self, ctx: Context, ev: NodesCreatedEvent) -> ParsedNodesEvent:
        """Step 2: Pass-through parsing (nodes already generated)."""
        step_start = time.perf_counter()
        file_path = ev.file_path
        node_count = len(ev.nodes)
        logger.info("[Workflow] Entering parse step for %s (%d nodes)", file_path, node_count)
        logger.debug(
            "[Workflow] Skipping parse step for %s; nodes supplied by loader (%d nodes)",
            file_path,
            node_count,
        )
        logger.info(
            "[Workflow] Parse step finished in %.2fs",
            time.perf_counter() - step_start,
        )
        return ParsedNodesEvent(nodes=ev.nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def validate_nodes(self, ctx: Context, ev: ParsedNodesEvent) -> ValidatedNodesEvent:
        """Step 2.5: Optional validation (currently no-op)."""
        step_start = time.perf_counter()
        if not WORKFLOW_ENABLE_VALIDATION:
            logger.info("[Workflow] Validation disabled; skipping (%.2fs)", time.perf_counter() - step_start)
            return ValidatedNodesEvent(nodes=ev.nodes, file_path=ev.file_path, metadata=ev.metadata)

        valid_nodes = [n for n in ev.nodes if n.get_content().strip()]
        if len(valid_nodes) != len(ev.nodes):
            logger.warning("[Workflow] Dropped %d empty nodes during validation", len(ev.nodes) - len(valid_nodes))
        logger.info(
            "[Workflow] Validation step finished in %.2fs (%d -> %d nodes)",
            time.perf_counter() - step_start,
            len(ev.nodes),
            len(valid_nodes),
        )
        return ValidatedNodesEvent(nodes=valid_nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def index_qdrant(self, ctx: Context, ev: ValidatedNodesEvent) -> QdrantIndexedEvent:
        """Step 3: Index nodes in Qdrant (optional)."""

        nodes = ev.nodes
        step_start = time.perf_counter()
        logger.info("[Workflow] Entering Qdrant step (enabled=%s)", self.enable_qdrant)
        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")

        if not self.enable_qdrant or not self.qdrant_indexer:
            logger.info(
                "[Workflow] Qdrant indexing disabled, skipping (%.2fs)",
                time.perf_counter() - step_start,
            )
            return QdrantIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Qdrant")

        try:
            self.qdrant_indexer(nodes)
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Qdrant")
            tracker.track_phase_stats(file_type, "qdrant_uploaded", len(nodes))
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Qdrant: {e}")
        finally:
            logger.info(
                "[Workflow] Qdrant step finished in %.2fs",
                time.perf_counter() - step_start,
            )

        return QdrantIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def index_elasticsearch(self, ctx: Context, ev: QdrantIndexedEvent) -> ElasticsearchIndexedEvent:
        """Step 4: Index nodes in Elasticsearch (optional)."""

        nodes = ev.nodes
        step_start = time.perf_counter()
        logger.info("[Workflow] Entering Elasticsearch step (enabled=%s)", self.enable_elasticsearch)
        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")

        if not self.enable_elasticsearch or not self.es_indexer:
            logger.info(
                "[Workflow] Elasticsearch indexing disabled, skipping (%.2fs)",
                time.perf_counter() - step_start,
            )
            return ElasticsearchIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Elasticsearch")

        try:
            self.es_indexer(nodes)
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Elasticsearch")
            tracker.track_phase_stats(file_type, "elasticsearch_uploaded", len(nodes))
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Elasticsearch: {e}")
        finally:
            logger.info(
                "[Workflow] Elasticsearch step finished in %.2fs",
                time.perf_counter() - step_start,
            )

        return ElasticsearchIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def index_neo4j(self, ctx: Context, ev: ElasticsearchIndexedEvent) -> Neo4jIndexedEvent:
        """Step 5: Index nodes in Neo4j knowledge graph (optional)."""

        nodes = ev.nodes
        step_start = time.perf_counter()
        logger.info("[Workflow] Entering Neo4j step (enabled=%s, mode=%s)", self.enable_neo4j, GRAPH_MODE)
        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")

        if GRAPH_MODE == "off":
            logger.info(
                "[Workflow] Graph mode set to 'off'; skipping (%.2fs)",
                time.perf_counter() - step_start,
            )
            return Neo4jIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

        if not self.enable_neo4j or not self.graph_ingestor:
            logger.info(
                "[Workflow] Neo4j indexing disabled, skipping (%.2fs)",
                time.perf_counter() - step_start,
            )
            return Neo4jIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Neo4j")

        try:
            use_property_graph = GRAPH_MODE in {"property", "legal", "schema"}
            self.graph_ingestor(nodes, use_property_graph=use_property_graph)
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Neo4j")
            tracker.track_phase_stats(file_type, "neo4j_uploaded", len(nodes))
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Neo4j: {e}")
        finally:
            logger.info(
                "[Workflow] Neo4j step finished in %.2fs",
                time.perf_counter() - step_start,
            )

        return Neo4jIndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def finalize(self, ctx: Context, ev: Neo4jIndexedEvent) -> StopEvent:
        """Final step: Collect results and return."""
        step_start = time.perf_counter()
        nodes = ev.nodes or []
        file_path = ev.file_path

        result = {
            "success": True,
            "file_path": file_path,
            "nodes_count": len(nodes),
            "message": f"Ingestion complete: {len(nodes)} nodes processed",
            "node_ids": [getattr(node, "node_id", None) or getattr(node, "id_", None) for node in nodes],
        }

        if self.return_nodes:
            result["nodes"] = nodes

        logger.info(f"[Workflow] {result['message']}")
        logger.info(
            "[Workflow] Finalize step finished in %.2fs",
            time.perf_counter() - step_start,
        )

        return StopEvent(result=result)


# Convenience function
async def run_ingestion_workflow(
    file_path: str,
    metadata: Optional[Dict[str, Any]] = None,
    return_nodes: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """Run the ingestion workflow for a file.

    Args:
        file_path: Path to file or YouTube URL
        metadata: Additional metadata dict
        **kwargs: Additional workflow options (enable_qdrant, enable_neo4j, etc.)

    Returns:
        Result dictionary with success status and stats

    Example:
        >>> result = await run_ingestion_workflow(
        ...     file_path="/path/to/document.pdf",
        ...     metadata={"source": "upload", "author": "John Doe"},
        ...     enable_qdrant=True,
        ...     enable_neo4j=True,
        ... )
        >>> print(result)
        {'success': True, 'nodes_count': 42, 'message': '...'}
    """
    if "return_nodes" in kwargs:
        return_nodes = bool(kwargs.pop("return_nodes"))

    workflow = IngestionWorkflow(return_nodes=return_nodes, **kwargs)

    result = await workflow.run(
        file_path=file_path,
        metadata=metadata or {},
    )

    return result


# ============================================================================
# Simple Pipeline API (Convenience Wrapper)
# ============================================================================


class SimpleIngestionPipeline:
    """Simplified ingestion API for quick document processing.

    Provides an easy-to-use interface that wraps the full IngestionWorkflow
    for common use cases where you just want to process files quickly.

    Example - Basic Usage:
        >>> pipeline = SimpleIngestionPipeline()
        >>> nodes = await pipeline.run(file_path="document.pdf")
        >>> print(f"Created {len(nodes)} nodes")

    Example - With Options:
        >>> pipeline = SimpleIngestionPipeline(enable_qdrant=True, enable_neo4j=True)
        >>> nodes = await pipeline.run_batch(file_paths=["doc1.pdf", "doc2.pdf"])
    """

    def __init__(self, **workflow_options):
        """Initialize simple pipeline.

        Args:
            **workflow_options: Any options passed to IngestionWorkflow
        """
        self.workflow_options = workflow_options

    async def run(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[BaseNode]:
        """Process a single file and return nodes.

        Args:
            file_path: Path to file or YouTube URL
            metadata: Optional metadata dict

        Returns:
            List of created nodes
        """
        result = await run_ingestion_workflow(
            file_path=file_path,
            metadata=metadata,
            **{**self.workflow_options, "return_nodes": True},
        )

        # Extract nodes from result
        nodes = result.get("nodes")
        if nodes is None:
            logger.warning("Ingestion workflow did not return nodes; falling back to node_ids")
            return result.get("node_ids", [])
        return nodes

    async def run_batch(
        self,
        file_paths: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
    ) -> List[List[BaseNode]]:
        """Process multiple files and return list of node lists.

        Args:
            file_paths: List of file paths or YouTube URLs
            metadata_list: Optional list of metadata dicts (one per file)

        Returns:
            List of node lists (one per file)
        """
        if metadata_list is None:
            metadata_list = [None] * len(file_paths)

        results = []
        for file_path, metadata in zip(file_paths, metadata_list):
            nodes = await self.run(file_path, metadata)
            results.append(nodes)

        return results


def create_simple_pipeline(**options) -> SimpleIngestionPipeline:
    """Factory function to create SimpleIngestionPipeline.

    Args:
        **options: Workflow options

    Returns:
        Configured SimpleIngestionPipeline

    Example:
        >>> pipeline = create_simple_pipeline(enable_qdrant=True)
    """
    return SimpleIngestionPipeline(**options)
