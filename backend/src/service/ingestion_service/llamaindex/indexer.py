"""Unified indexer for Qdrant, Elasticsearch, and Neo4j.

Consolidates vector and graph indexing into a single module.
Based on LlamaIndex best practices from official tutorials.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.vector_stores.elasticsearch import ElasticsearchStore
from llama_index.vector_stores.qdrant import QdrantVectorStore

from .property_graph_ingestor import LegalPropertyGraphIngestor

logger = logging.getLogger(__name__)


def _get_bool_env(name: str, default: bool = False) -> bool:
    """Parse boolean from environment variable."""
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}


def _ensure_text_node(node: BaseNode) -> TextNode:
    """Convert BaseNode to TextNode if needed."""
    if isinstance(node, TextNode):
        return node
    return TextNode(
        text=node.get_content(),
        metadata=dict(node.metadata or {}),
        id_=getattr(node, "node_id", None)
    )


# ============================================================================
# Storage Context Creation
# ============================================================================

def create_storage_context(
    qdrant_store: Optional[QdrantVectorStore] = None,
    elasticsearch_store: Optional[ElasticsearchStore] = None,
    neo4j_graph_store: Optional[Neo4jPropertyGraphStore] = None,
    docstore: Optional[SimpleDocumentStore] = None,
) -> StorageContext:
    """Create unified StorageContext for all stores.
    
    Example:
        >>> qdrant = create_qdrant_store()
        >>> storage_ctx = create_storage_context(qdrant_store=qdrant)
        >>> index = VectorStoreIndex.from_documents(docs, storage_context=storage_ctx)
    """
    logger.info("Creating unified storage context")
    
    if docstore is None:
        docstore = SimpleDocumentStore()
    
    # Primary vector store (prefer Qdrant)
    primary_vector_store = qdrant_store or elasticsearch_store
    
    if primary_vector_store is None:
        logger.warning("No vector store provided to StorageContext")
    
    return StorageContext.from_defaults(
        vector_store=primary_vector_store,
        graph_store=neo4j_graph_store,
        docstore=docstore,
    )


# ============================================================================
# Vector Store Creation
# ============================================================================

def create_qdrant_store(
    collection_name: Optional[str] = None,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    enable_hybrid: Optional[bool] = None,
) -> QdrantVectorStore:
    """Create Qdrant vector store with optional hybrid search.
    
    Args:
        collection_name: Collection name (default from env)
        url: Qdrant URL (default from env)
        api_key: API key (default from env)
        enable_hybrid: Enable hybrid search with sparse vectors (default from env)
        
    Returns:
        Configured QdrantVectorStore
    """
    collection_name = collection_name or os.getenv("QDRANT_CLUSTER_ID", "documents")
    url = url or os.getenv("QDRANT_ENDPOINT", "http://localhost:6333")
    api_key = api_key or os.getenv("QDRANT_API_KEY")
    
    if enable_hybrid is None:
        enable_hybrid = _get_bool_env("QDRANT_ENABLE_HYBRID", False)
    
    sparse_model = os.getenv("QDRANT_SPARSE_MODEL", "Qdrant/bm25") if enable_hybrid else None
    
    logger.info(f"Creating Qdrant store: {collection_name} (hybrid={enable_hybrid})")
    
    return QdrantVectorStore(
        collection_name=collection_name,
        url=url,
        api_key=api_key,
        enable_hybrid=enable_hybrid,
        fastembed_sparse_model=sparse_model,
    )


def create_elasticsearch_store(
    index_name: Optional[str] = None,
    es_url: Optional[str] = None,
) -> ElasticsearchStore:
    """Create Elasticsearch vector store.
    
    Args:
        index_name: Index name (default from env)
        es_url: Elasticsearch URL (default from env)
        
    Returns:
        Configured ElasticsearchStore
    """
    index_name = index_name or os.getenv("ES_INDEX", "documents")
    es_url = es_url or os.getenv("ES_HOST", "http://localhost:9200")
    
    logger.info(f"Creating Elasticsearch store: {index_name}")
    
    return ElasticsearchStore(
        index_name=index_name,
        es_url=es_url,
    )


# ============================================================================
# Unified Indexing Functions
# ============================================================================

def index_nodes_to_qdrant(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    collection_name: Optional[str] = None,
) -> Optional[QdrantVectorStore]:
    """Index nodes to Qdrant vector store.
    
    Args:
        nodes: Nodes to index
        embed_model: Embedding model (creates OpenAI embedder if None)
        collection_name: Collection name (uses env default if None)
        
    Returns:
        QdrantVectorStore instance or None if indexing disabled
    """
    if not nodes:
        logger.warning("No nodes to index to Qdrant")
        return None
    
    # Check if Qdrant is enabled
    if not _get_bool_env("QDRANT_ENABLE", True):
        logger.info("Qdrant indexing disabled")
        return None
    
    try:
        # Create store
        vector_store = create_qdrant_store(collection_name=collection_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Create embedder
        embedder = None
        if embed_model is not None:
            model_name = (
                getattr(embed_model, "model", None) or
                getattr(embed_model, "model_name", None) or
                "text-embedding-3-small"
            )
            embedder = OpenAIEmbedding(
                model_name=model_name,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        
        # Convert to TextNodes
        text_nodes = [_ensure_text_node(node) for node in nodes]
        
        # Create index (automatically indexes)
        VectorStoreIndex(
            nodes=text_nodes,
            storage_context=storage_context,
            embed_model=embedder,
        )
        
        logger.info(f"✅ Indexed {len(text_nodes)} nodes to Qdrant")
        return vector_store
        
    except Exception as e:
        logger.error(f"Failed to index to Qdrant: {e}")
        return None


def index_nodes_to_elasticsearch(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    index_name: Optional[str] = None,
) -> Optional[ElasticsearchStore]:
    """Index nodes to Elasticsearch.
    
    Args:
        nodes: Nodes to index
        embed_model: Embedding model (creates OpenAI embedder if None)
        index_name: Index name (uses env default if None)
        
    Returns:
        ElasticsearchStore instance or None if indexing disabled
    """
    if not nodes:
        logger.warning("No nodes to index to Elasticsearch")
        return None
    
    # Check if ES is enabled
    if not _get_bool_env("ES_LI_ENABLE", False):
        logger.info("Elasticsearch indexing disabled")
        return None
    
    try:
        # Create store
        vector_store = create_elasticsearch_store(index_name=index_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Create embedder
        embedder = None
        if embed_model is not None:
            model_name = (
                getattr(embed_model, "model", None) or
                getattr(embed_model, "model_name", None) or
                "text-embedding-3-small"
            )
            embedder = OpenAIEmbedding(
                model_name=model_name,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        
        # Convert to TextNodes
        text_nodes = [_ensure_text_node(node) for node in nodes]
        
        # Create index (automatically indexes)
        VectorStoreIndex(
            nodes=text_nodes,
            storage_context=storage_context,
            embed_model=embedder,
        )
        
        logger.info(f"✅ Indexed {len(text_nodes)} nodes to Elasticsearch")
        return vector_store
        
    except Exception as e:
        logger.error(f"Failed to index to Elasticsearch: {e}")
        return None


def index_nodes_to_neo4j(
    nodes: List[BaseNode],
    use_property_graph: bool = True,
) -> int:
    """Index nodes to Neo4j knowledge graph.
    
    Args:
        nodes: Nodes to index
        use_property_graph: Use PropertyGraphIndex with legal schema
        
    Returns:
        Number of nodes indexed
    """
    if not nodes:
        logger.warning("No nodes to index to Neo4j")
        return 0
    
    # Check if graph indexing is enabled
    if not _get_bool_env("GRAPH_LI_ENABLE", False):
        logger.info("Neo4j indexing disabled")
        return 0
    
    try:
        if use_property_graph:
            # Use legal domain property graph
            ingestor = LegalPropertyGraphIngestor()
            return ingestor.ingest_nodes(nodes)
        else:
            # Fallback to basic graph indexing (not implemented here)
            logger.warning("Basic graph indexing not implemented, use property_graph=True")
            return 0
            
    except Exception as e:
        logger.error(f"Failed to index to Neo4j: {e}")
        return 0


def index_nodes(
    nodes: List[BaseNode],
    embed_model: Optional[object] = None,
    enable_qdrant: bool = True,
    enable_elasticsearch: bool = False,
    enable_neo4j: bool = False,
) -> dict:
    """Index nodes to all enabled stores.
    
    Convenience function that indexes to multiple stores at once.
    
    Args:
        nodes: Nodes to index
        embed_model: Embedding model
        enable_qdrant: Index to Qdrant
        enable_elasticsearch: Index to Elasticsearch
        enable_neo4j: Index to Neo4j
        
    Returns:
        Dict with indexing results for each store
    """
    results = {}
    
    if enable_qdrant:
        qdrant_store = index_nodes_to_qdrant(nodes, embed_model)
        results["qdrant"] = qdrant_store is not None
    
    if enable_elasticsearch:
        es_store = index_nodes_to_elasticsearch(nodes, embed_model)
        results["elasticsearch"] = es_store is not None
    
    if enable_neo4j:
        neo4j_count = index_nodes_to_neo4j(nodes)
        results["neo4j"] = neo4j_count > 0
    
    return results


# Backward compatibility aliases
upload_to_qdrant_llamaindex = index_nodes_to_qdrant
upload_to_elasticsearch_llamaindex = index_nodes_to_elasticsearch
graph_rag_ingest_llamaindex = index_nodes_to_neo4j
