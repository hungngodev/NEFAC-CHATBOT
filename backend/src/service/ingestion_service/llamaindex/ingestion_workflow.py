"""LlamaIndex Workflow for durable ingestion pipeline.

Based on: https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from llama_index.core import Document as LIDocument
from llama_index.core import Settings
from llama_index.core.schema import BaseNode
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.openai import OpenAI
from pydantic import Field

from ..settings import (
    GRAPH_MODE,
    LLAMAPARSE_API_KEY,
    LLAMAPARSE_AUTO_MODE,
    LLAMAPARSE_BBOX_BOTTOM,
    LLAMAPARSE_BBOX_TOP,
    LLAMAPARSE_DO_NOT_UNROLL_COLUMNS,
    LLAMAPARSE_ENABLE,
    LLAMAPARSE_EXTRACT_CHARTS,
    LLAMAPARSE_INVALIDATE_CACHE,
    LLAMAPARSE_LANGUAGE,
    LLAMAPARSE_RESULT_TYPE,
    LLAMAPARSE_SKIP_DIAGONAL_TEXT,
    LLAMAPARSE_TARGET_PAGES,
    LLAMAPARSE_USER_PROMPT,
    WORKFLOW_ENABLE_MODEL_FALLBACK,
    WORKFLOW_ENABLE_VALIDATION,
    WORKFLOW_FALLBACK_MODEL,
    WORKFLOW_MAX_RETRIES,
)
from .document_loader import UnifiedDocumentLoader
from .indexer import index_nodes_to_elasticsearch, index_nodes_to_neo4j, index_nodes_to_qdrant
from .node_parser import ContextualNodeParser

logger = logging.getLogger(__name__)


# Custom Events for workflow steps
class DocumentLoadedEvent(Event):
    """Event emitted when documents are loaded."""

    documents: List[LIDocument]
    file_path: str


class NodesCreatedEvent(Event):
    """Event emitted when nodes are created from documents."""

    nodes: List[BaseNode]


class NodeValidationEvent(Event):
    """Event emitted for node validation with retry support."""

    nodes: List[BaseNode]
    retry_count: int = 0
    validation_errors: List[str] = Field(default_factory=list)


class RetryParsingEvent(Event):
    """Event emitted when parsing needs retry with fallback model."""

    documents: List[LIDocument]
    retry_count: int
    error: str
    use_fallback_model: bool = False


class VectorIndexingCompleteEvent(Event):
    """Event emitted when vector indexing completes."""

    success: bool
    message: str
    node_count: int


class GraphIndexingCompleteEvent(Event):
    """Event emitted when graph indexing completes."""

    success: bool
    message: str
    node_count: int


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
        enable_contextual_retrieval: bool = True,
        enable_metadata_extraction: bool = False,
        use_llamaparse: bool = False,
        timeout: int = 3600,
        return_nodes: bool = False,
        **kwargs,
    ):
        """Initialize ingestion workflow.

        Args:
            enable_qdrant: Enable Qdrant vector indexing
            enable_elasticsearch: Enable Elasticsearch hybrid indexing
            enable_neo4j: Enable Neo4j knowledge graph
            enable_contextual_retrieval: Enable contextual summaries
            enable_metadata_extraction: Enable LLM metadata extraction
            use_llamaparse: Use LlamaParse for PDFs
            timeout: Workflow timeout in seconds
            return_nodes: Include parsed nodes in the final StopEvent payload
        """
        super().__init__(timeout=timeout, **kwargs)

        self.enable_qdrant = enable_qdrant
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_neo4j = enable_neo4j
        self.enable_contextual_retrieval = enable_contextual_retrieval
        self.enable_metadata_extraction = enable_metadata_extraction
        self.use_llamaparse = use_llamaparse
        self.return_nodes = return_nodes

        # Lazy init components (only when needed)
        self._loader = None
        self._parser = None
        self._qdrant_indexer = None
        self._es_indexer = None
        self._graph_ingestor = None

    @property
    def loader(self):
        """Lazy load document loader with all LlamaParse options."""
        if self._loader is None:
            self._loader = UnifiedDocumentLoader(
                use_llamaparse=self.use_llamaparse or LLAMAPARSE_ENABLE,
                llamaparse_api_key=LLAMAPARSE_API_KEY,
                llamaparse_auto_mode=LLAMAPARSE_AUTO_MODE,
                llamaparse_extract_charts=LLAMAPARSE_EXTRACT_CHARTS,
                llamaparse_result_type=LLAMAPARSE_RESULT_TYPE,
                llamaparse_target_pages=LLAMAPARSE_TARGET_PAGES,
                llamaparse_bbox_top=LLAMAPARSE_BBOX_TOP,
                llamaparse_bbox_bottom=LLAMAPARSE_BBOX_BOTTOM,
                llamaparse_user_prompt=LLAMAPARSE_USER_PROMPT,
                llamaparse_invalidate_cache=LLAMAPARSE_INVALIDATE_CACHE,
                llamaparse_language=LLAMAPARSE_LANGUAGE,
                llamaparse_skip_diagonal_text=LLAMAPARSE_SKIP_DIAGONAL_TEXT,
                llamaparse_do_not_unroll_columns=LLAMAPARSE_DO_NOT_UNROLL_COLUMNS,
                fallback_to_unstructured=True,
            )
        return self._loader

    @property
    def parser(self):
        """Lazy load contextual node parser."""
        if self._parser is None:
            self._parser = ContextualNodeParser(
                enable_contextual_retrieval=self.enable_contextual_retrieval,
                enable_metadata_extraction=self.enable_metadata_extraction,
            )
        return self._parser

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
    async def load_documents(self, ctx: Context, ev: StartEvent) -> DocumentLoadedEvent | StopEvent:
        """Step 1: Load documents from file path.

        Input: file_path, metadata
        Output: DocumentLoadedEvent with loaded documents
        """

        file_path = ev.get("file_path")
        metadata = ev.get("metadata", {})

        if not file_path:
            return StopEvent(result={"success": False, "error": "No file_path provided"})

        logger.info(f"[Workflow] Loading document: {file_path}")

        try:
            # Check if it's a YouTube URL
            if "youtube.com" in str(file_path) or "youtu.be" in str(file_path):
                documents = self.loader.load_youtube(file_path, extra_info=metadata)
            else:
                documents = self.loader.load_file(file_path, extra_info=metadata)

            if not documents:
                return StopEvent(result={"success": False, "error": "No documents loaded"})

            await ctx.set("documents", documents)
            await ctx.set("file_path", file_path)

            logger.info(f"[Workflow] Loaded {len(documents)} documents")

            return DocumentLoadedEvent(documents=documents, file_path=str(file_path))

        except Exception as e:
            logger.error(f"[Workflow] Failed to load documents: {e}")
            return StopEvent(result={"success": False, "error": str(e)})

    @step
    async def parse_nodes(self, ctx: Context, ev: DocumentLoadedEvent | RetryParsingEvent) -> NodesCreatedEvent | RetryParsingEvent | StopEvent:
        """Step 2: Parse documents into nodes with contextual summaries.

        Enhanced with model fallback from tutorial:
        https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch

        Input: DocumentLoadedEvent or RetryParsingEvent
        Output: NodesCreatedEvent with parsed nodes, or RetryParsingEvent, or StopEvent
        """
        # Handle both event types
        if isinstance(ev, RetryParsingEvent):
            documents = ev.documents
            retry_count = ev.retry_count
            use_fallback = ev.use_fallback_model
        else:
            documents = ev.documents
            retry_count = 0
            use_fallback = False

        logger.info(f"[Workflow] Parsing {len(documents)} documents into nodes (retry={retry_count})")

        try:
            # Use fallback model if requested and enabled
            if use_fallback and WORKFLOW_ENABLE_MODEL_FALLBACK:
                logger.info(f"[Workflow] Using fallback model: {WORKFLOW_FALLBACK_MODEL}")
                # Switch to fallback model temporarily
                original_llm = Settings.llm
                Settings.llm = OpenAI(model=WORKFLOW_FALLBACK_MODEL)
                try:
                    nodes = self.parser.build_nodes_from_documents(documents, show_progress=True)
                finally:
                    Settings.llm = original_llm
            else:
                nodes = self.parser.build_nodes_from_documents(documents, show_progress=True)

            if not nodes:
                # Retry if under limit
                if retry_count < WORKFLOW_MAX_RETRIES:
                    logger.warning(f"[Workflow] No nodes created, retrying ({retry_count + 1}/{WORKFLOW_MAX_RETRIES})")
                    return RetryParsingEvent(documents=documents, retry_count=retry_count + 1, error="No nodes created", use_fallback_model=WORKFLOW_ENABLE_MODEL_FALLBACK and not use_fallback)
                else:
                    return StopEvent(result={"success": False, "error": "No nodes created after max retries"})

            await ctx.set("nodes", nodes)
            logger.info(f"[Workflow] Created {len(nodes)} nodes")

            # Validate nodes before proceeding
            return NodeValidationEvent(nodes=nodes, retry_count=0)

        except Exception as e:
            logger.error(f"[Workflow] Failed to parse nodes: {e}")

            # Retry with fallback model if enabled and not already using it
            if retry_count < WORKFLOW_MAX_RETRIES and WORKFLOW_ENABLE_MODEL_FALLBACK and not use_fallback:
                logger.warning("[Workflow] Retrying with fallback model")
                return RetryParsingEvent(documents=documents, retry_count=retry_count + 1, error=str(e), use_fallback_model=True)

            return StopEvent(result={"success": False, "error": str(e)})

    @step
    async def validate_nodes(self, ctx: Context, ev: NodeValidationEvent) -> NodesCreatedEvent | RetryParsingEvent | StopEvent:
        """Step 2.5: Validate nodes with auto-correction.

        Enhanced with validation from tutorial:
        https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch

        Input: NodeValidationEvent
        Output: NodesCreatedEvent if valid, RetryParsingEvent if needs retry, StopEvent if failed
        """
        nodes = ev.nodes
        retry_count = ev.retry_count

        if not WORKFLOW_ENABLE_VALIDATION:
            logger.info("[Workflow] Node validation disabled, skipping")
            return NodesCreatedEvent(nodes=nodes)

        logger.info(f"[Workflow] Validating {len(nodes)} nodes")

        validation_errors = []

        # Check for empty nodes
        empty_nodes = [n for n in nodes if not n.get_content().strip()]
        if empty_nodes:
            validation_errors.append(f"Found {len(empty_nodes)} empty nodes")

        # Check for extremely short nodes (might indicate parsing issues)
        short_nodes = [n for n in nodes if len(n.get_content().strip()) < 10]
        if short_nodes:
            validation_errors.append(f"Found {len(short_nodes)} nodes with <10 characters")

        if validation_errors:
            logger.warning(f"[Workflow] Validation issues: {', '.join(validation_errors)}")

            # If we have valid nodes, filter out invalid ones
            valid_nodes = [n for n in nodes if n.get_content().strip() and len(n.get_content().strip()) >= 10]

            if valid_nodes and len(valid_nodes) > len(nodes) * 0.5:
                # More than 50% are valid, proceed with valid nodes only
                logger.info(f"[Workflow] Proceeding with {len(valid_nodes)}/{len(nodes)} valid nodes")
                return NodesCreatedEvent(nodes=valid_nodes)

            # Too many invalid nodes, retry if under limit
            if retry_count < WORKFLOW_MAX_RETRIES:
                logger.warning("[Workflow] Too many invalid nodes, retrying with adjusted settings")
                # Get original documents for retry
                documents = await ctx.get("documents", default=[])
                if documents:
                    return RetryParsingEvent(documents=documents, retry_count=retry_count + 1, error="; ".join(validation_errors), use_fallback_model=True)

            return StopEvent(result={"success": False, "error": f"Validation failed: {'; '.join(validation_errors)}"})

        logger.info(f"[Workflow] Validation passed for {len(nodes)} nodes")
        return NodesCreatedEvent(nodes=nodes)

    @step
    async def index_qdrant(self, ctx: Context, ev: NodesCreatedEvent) -> VectorIndexingCompleteEvent:
        """Step 3: Index nodes in Qdrant (optional).

        Input: NodesCreatedEvent
        Output: VectorIndexingCompleteEvent
        """

        if not self.enable_qdrant or not self.qdrant_indexer:
            logger.info("[Workflow] Qdrant indexing disabled, skipping")
            return VectorIndexingCompleteEvent(success=True, message="Qdrant indexing skipped (disabled)", node_count=0)

        nodes = ev.nodes

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Qdrant")

        try:
            self.qdrant_indexer(nodes)

            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Qdrant")

            return VectorIndexingCompleteEvent(success=True, message=f"Indexed {len(nodes)} nodes in Qdrant", node_count=len(nodes))

        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Qdrant: {e}")
            # Don't stop workflow, continue to next step
            return VectorIndexingCompleteEvent(success=False, message=str(e), node_count=0)

    @step
    async def index_elasticsearch(self, ctx: Context, ev: NodesCreatedEvent) -> VectorIndexingCompleteEvent:
        """Step 4: Index nodes in Elasticsearch (optional).

        Input: NodesCreatedEvent
        Output: VectorIndexingCompleteEvent
        """

        if not self.enable_elasticsearch or not self.es_indexer:
            logger.info("[Workflow] Elasticsearch indexing disabled, skipping")
            return VectorIndexingCompleteEvent(success=True, message="Elasticsearch indexing skipped (disabled)", node_count=0)

        nodes = ev.nodes

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Elasticsearch")

        try:
            self.es_indexer(nodes)

            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Elasticsearch")

            return VectorIndexingCompleteEvent(success=True, message=f"Indexed {len(nodes)} nodes in Elasticsearch", node_count=len(nodes))

        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Elasticsearch: {e}")
            return VectorIndexingCompleteEvent(success=False, message=str(e), node_count=0)

    @step
    async def index_neo4j(self, ctx: Context, ev: NodesCreatedEvent) -> GraphIndexingCompleteEvent:
        """Step 5: Index nodes in Neo4j knowledge graph (optional).

        Input: NodesCreatedEvent
        Output: GraphIndexingCompleteEvent
        """

        if GRAPH_MODE == "off":
            logger.info("[Workflow] Graph mode set to 'off'; skipping")
            return GraphIndexingCompleteEvent(
                success=True,
                message="Graph indexing skipped (mode=off)",
                node_count=0,
            )

        if not self.enable_neo4j or not self.graph_ingestor:
            logger.info("[Workflow] Neo4j indexing disabled, skipping")
            return GraphIndexingCompleteEvent(success=True, message="Neo4j indexing skipped (disabled)", node_count=0)

        nodes = ev.nodes

        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Neo4j")

        try:
            use_property_graph = GRAPH_MODE in {"property", "legal", "schema"}
            self.graph_ingestor(nodes, use_property_graph=use_property_graph)

            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Neo4j")

            return GraphIndexingCompleteEvent(success=True, message=f"Indexed {len(nodes)} nodes in Neo4j", node_count=len(nodes))

        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Neo4j: {e}")
            return GraphIndexingCompleteEvent(success=False, message=str(e), node_count=0)

    @step
    async def finalize(self, ctx: Context, ev: VectorIndexingCompleteEvent | GraphIndexingCompleteEvent) -> StopEvent:
        """Final step: Collect results and return.

        Input: Any completion event
        Output: StopEvent with final results
        """

        nodes = await ctx.get("nodes", default=[])
        file_path = await ctx.get("file_path", default="unknown")

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
        ...     enable_contextual_retrieval=True,
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
        >>> pipeline = SimpleIngestionPipeline(
        ...     enable_contextual_retrieval=True,
        ...     enable_qdrant=True,
        ...     enable_neo4j=True,
        ... )
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
        >>> pipeline = create_simple_pipeline(
        ...     enable_qdrant=True,
        ...     enable_contextual_retrieval=True
        ... )
    """
    return SimpleIngestionPipeline(**options)
