"""LlamaIndex Workflow for durable ingestion pipeline.

Based on: https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    step,
    Context,
    Event,
)
from llama_index.core import Document as LIDocument
from llama_index.core.schema import BaseNode

logger = logging.getLogger(__name__)


# Custom Events for workflow steps
class DocumentLoadedEvent(Event):
    """Event emitted when documents are loaded."""
    documents: List[LIDocument]
    file_path: str


class NodesCreatedEvent(Event):
    """Event emitted when nodes are created from documents."""
    nodes: List[BaseNode]


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
        """
        super().__init__(timeout=timeout, **kwargs)
        
        self.enable_qdrant = enable_qdrant
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_neo4j = enable_neo4j
        self.enable_contextual_retrieval = enable_contextual_retrieval
        self.enable_metadata_extraction = enable_metadata_extraction
        self.use_llamaparse = use_llamaparse
        
        # Lazy init components (only when needed)
        self._loader = None
        self._parser = None
        self._qdrant_indexer = None
        self._es_indexer = None
        self._graph_ingestor = None
    
    @property
    def loader(self):
        """Lazy load document loader."""
        if self._loader is None:
            from .document_loader import UnifiedDocumentLoader
            self._loader = UnifiedDocumentLoader(
                use_llamaparse=self.use_llamaparse,
                fallback_to_unstructured=True,
            )
        return self._loader
    
    @property
    def parser(self):
        """Lazy load contextual node parser."""
        if self._parser is None:
            from .node_parser import ContextualNodeParser
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
                from .indexer import index_nodes_to_qdrant
                self._qdrant_indexer = index_nodes_to_qdrant
            except ImportError as e:
                logger.warning(f"Qdrant indexer not available: {e}")
        return self._qdrant_indexer
    
    @property
    def es_indexer(self):
        """Lazy load Elasticsearch indexer."""
        if self._es_indexer is None and self.enable_elasticsearch:
            try:
                from .indexer import index_nodes_to_elasticsearch
                self._es_indexer = index_nodes_to_elasticsearch
            except ImportError as e:
                logger.warning(f"Elasticsearch indexer not available: {e}")
        return self._es_indexer
    
    @property
    def graph_ingestor(self):
        """Lazy load graph ingestor."""
        if self._graph_ingestor is None and self.enable_neo4j:
            try:
                from .indexer import index_nodes_to_neo4j
                self._graph_ingestor = index_nodes_to_neo4j
            except ImportError as e:
                logger.warning(f"Graph ingestor not available: {e}")
        return self._graph_ingestor
    
    @step
    async def load_documents(
        self, 
        ctx: Context, 
        ev: StartEvent
    ) -> DocumentLoadedEvent | StopEvent:
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
    async def parse_nodes(
        self, 
        ctx: Context, 
        ev: DocumentLoadedEvent
    ) -> NodesCreatedEvent | StopEvent:
        """Step 2: Parse documents into nodes with contextual summaries.
        
        Input: DocumentLoadedEvent
        Output: NodesCreatedEvent with parsed nodes
        """
        
        documents = ev.documents
        
        logger.info(f"[Workflow] Parsing {len(documents)} documents into nodes")
        
        try:
            nodes = self.parser.build_nodes_from_documents(documents, show_progress=True)
            
            if not nodes:
                return StopEvent(result={"success": False, "error": "No nodes created"})
            
            await ctx.set("nodes", nodes)
            
            logger.info(f"[Workflow] Created {len(nodes)} nodes")
            
            return NodesCreatedEvent(nodes=nodes)
        
        except Exception as e:
            logger.error(f"[Workflow] Failed to parse nodes: {e}")
            return StopEvent(result={"success": False, "error": str(e)})
    
    @step
    async def index_qdrant(
        self, 
        ctx: Context, 
        ev: NodesCreatedEvent
    ) -> VectorIndexingCompleteEvent:
        """Step 3: Index nodes in Qdrant (optional).
        
        Input: NodesCreatedEvent
        Output: VectorIndexingCompleteEvent
        """
        
        if not self.enable_qdrant or not self.qdrant_indexer:
            logger.info("[Workflow] Qdrant indexing disabled, skipping")
            return VectorIndexingCompleteEvent(
                success=True,
                message="Qdrant indexing skipped (disabled)",
                node_count=0
            )
        
        nodes = ev.nodes
        
        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Qdrant")
        
        try:
            self.qdrant_indexer(nodes)
            
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Qdrant")
            
            return VectorIndexingCompleteEvent(
                success=True,
                message=f"Indexed {len(nodes)} nodes in Qdrant",
                node_count=len(nodes)
            )
        
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Qdrant: {e}")
            # Don't stop workflow, continue to next step
            return VectorIndexingCompleteEvent(
                success=False,
                message=str(e),
                node_count=0
            )
    
    @step
    async def index_elasticsearch(
        self, 
        ctx: Context, 
        ev: NodesCreatedEvent
    ) -> VectorIndexingCompleteEvent:
        """Step 4: Index nodes in Elasticsearch (optional).
        
        Input: NodesCreatedEvent
        Output: VectorIndexingCompleteEvent
        """
        
        if not self.enable_elasticsearch or not self.es_indexer:
            logger.info("[Workflow] Elasticsearch indexing disabled, skipping")
            return VectorIndexingCompleteEvent(
                success=True,
                message="Elasticsearch indexing skipped (disabled)",
                node_count=0
            )
        
        nodes = ev.nodes
        
        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Elasticsearch")
        
        try:
            self.es_indexer(nodes)
            
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Elasticsearch")
            
            return VectorIndexingCompleteEvent(
                success=True,
                message=f"Indexed {len(nodes)} nodes in Elasticsearch",
                node_count=len(nodes)
            )
        
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Elasticsearch: {e}")
            return VectorIndexingCompleteEvent(
                success=False,
                message=str(e),
                node_count=0
            )
    
    @step
    async def index_neo4j(
        self, 
        ctx: Context, 
        ev: NodesCreatedEvent
    ) -> GraphIndexingCompleteEvent:
        """Step 5: Index nodes in Neo4j knowledge graph (optional).
        
        Input: NodesCreatedEvent
        Output: GraphIndexingCompleteEvent
        """
        
        if not self.enable_neo4j or not self.graph_ingestor:
            logger.info("[Workflow] Neo4j indexing disabled, skipping")
            return GraphIndexingCompleteEvent(
                success=True,
                message="Neo4j indexing skipped (disabled)",
                node_count=0
            )
        
        nodes = ev.nodes
        
        logger.info(f"[Workflow] Indexing {len(nodes)} nodes in Neo4j")
        
        try:
            self.graph_ingestor(nodes, use_property_graph=True)
            
            logger.info(f"[Workflow] Successfully indexed {len(nodes)} nodes in Neo4j")
            
            return GraphIndexingCompleteEvent(
                success=True,
                message=f"Indexed {len(nodes)} nodes in Neo4j",
                node_count=len(nodes)
            )
        
        except Exception as e:
            logger.error(f"[Workflow] Failed to index in Neo4j: {e}")
            return GraphIndexingCompleteEvent(
                success=False,
                message=str(e),
                node_count=0
            )
    
    @step
    async def finalize(
        self, 
        ctx: Context, 
        ev: VectorIndexingCompleteEvent | GraphIndexingCompleteEvent
    ) -> StopEvent:
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
            "message": f"Ingestion complete: {len(nodes)} nodes processed"
        }
        
        logger.info(f"[Workflow] {result['message']}")
        
        return StopEvent(result=result)


# Convenience function
async def run_ingestion_workflow(
    file_path: str,
    metadata: Optional[Dict[str, Any]] = None,
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
    workflow = IngestionWorkflow(**kwargs)
    
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
            **self.workflow_options
        )
        
        # Extract nodes from result
        return result.get("nodes", [])
    
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
