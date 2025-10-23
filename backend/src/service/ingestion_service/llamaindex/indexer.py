"""Unified indexer for Qdrant, Elasticsearch, and Neo4j.

Consolidates vector and graph indexing into a single module.
Based on LlamaIndex best practices from official tutorials.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from llama_index.core import Settings, StorageContext, VectorStoreIndex
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
    return TextNode(text=node.get_content(), metadata=dict(node.metadata or {}), id_=getattr(node, "node_id", None))


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


def relative_score_fusion(dense_scores, sparse_scores, alpha: float = 0.5):
    """Relative score fusion algorithm for hybrid search.

    Based on: https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/

    Normalizes scores to [0,1] and combines with weighted average.

    Args:
        dense_scores: List of (id, dense_score) tuples
        sparse_scores: List of (id, sparse_score) tuples
        alpha: Weight for dense scores (1-alpha for sparse). Range [0,1]
               alpha=1.0 means pure dense, alpha=0.0 means pure sparse

    Returns:
        List of (id, combined_score) tuples sorted by score descending
    """
    if not dense_scores and not sparse_scores:
        return []

    # Normalize dense scores
    max_dense = max((score for _, score in dense_scores), default=1.0)
    dense_normalized = {id_: score / max_dense for id_, score in dense_scores} if max_dense > 0 else {}

    # Normalize sparse scores
    max_sparse = max((score for _, score in sparse_scores), default=1.0)
    sparse_normalized = {id_: score / max_sparse for id_, score in sparse_scores} if max_sparse > 0 else {}

    # Combine with weighted average
    all_ids = set(dense_normalized.keys()) | set(sparse_normalized.keys())
    combined = {}

    for id_ in all_ids:
        dense_score = dense_normalized.get(id_, 0.0)
        sparse_score = sparse_normalized.get(id_, 0.0)
        combined[id_] = alpha * dense_score + (1 - alpha) * sparse_score

    # Sort by score descending
    return sorted(combined.items(), key=lambda x: x[1], reverse=True)


def create_qdrant_store(
    collection_name: Optional[str] = None,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    enable_hybrid: Optional[bool] = None,
    sparse_top_k: Optional[int] = None,
    hybrid_fusion_fn: Optional[object] = None,
) -> QdrantVectorStore:
    """Create Qdrant vector store with optional hybrid search.

    Enhanced with custom fusion from tutorial:
    https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/

    Args:
        collection_name: Collection name (default from env)
        url: Qdrant URL (default from env)
        api_key: API key (default from env)
        enable_hybrid: Enable hybrid search with sparse vectors (default from env)
        sparse_top_k: Number of sparse results to retrieve (default from env)
        hybrid_fusion_fn: Custom fusion function (default: relative_score_fusion)

    Returns:
        Configured QdrantVectorStore with hybrid search support
    """
    collection_name = collection_name or os.getenv("QDRANT_CLUSTER_ID", "documents")
    url = url or os.getenv("QDRANT_ENDPOINT", "http://localhost:6333")
    api_key = api_key or os.getenv("QDRANT_API_KEY")

    if enable_hybrid is None:
        enable_hybrid = _get_bool_env("QDRANT_ENABLE_HYBRID", False)

    if enable_hybrid:
        sparse_model = os.getenv("QDRANT_SPARSE_MODEL", "Qdrant/bm25")
        sparse_top_k = sparse_top_k or int(os.getenv("QDRANT_SPARSE_TOP_K", "100"))

        # Use custom fusion function if provided, otherwise use relative score fusion with alpha
        if hybrid_fusion_fn is None:
            alpha = float(os.getenv("QDRANT_HYBRID_ALPHA", "0.5"))
            fusion_algorithm = os.getenv("QDRANT_FUSION_ALGORITHM", "relative_score")

            if fusion_algorithm == "relative_score":

                def hybrid_fusion_fn(dense, sparse):
                    return relative_score_fusion(dense, sparse, alpha)

                logger.info(f"Using relative score fusion with alpha={alpha}")
            # Note: RRF fusion would be handled by Qdrant internally if supported

        logger.info(f"Creating Qdrant store: {collection_name} (hybrid=True, sparse_top_k={sparse_top_k})")

        kwargs = {
            "collection_name": collection_name,
            "url": url,
            "api_key": api_key,
            "enable_hybrid": True,
            "fastembed_sparse_model": sparse_model,
            "sparse_top_k": sparse_top_k,
        }

        # Add fusion function if supported by the version
        try:
            kwargs["hybrid_fusion_fn"] = hybrid_fusion_fn
        except TypeError:
            logger.debug("hybrid_fusion_fn not supported by this Qdrant version")

        return QdrantVectorStore(**kwargs)

    else:
        logger.info(f"Creating Qdrant store: {collection_name} (hybrid=False)")
        return QdrantVectorStore(
            collection_name=collection_name,
            url=url,
            api_key=api_key,
            enable_hybrid=False,
        )


def create_elasticsearch_store(
    index_name: Optional[str] = None,
    es_url: Optional[str] = None,
    strategy: Optional[str] = None,
) -> ElasticsearchStore:
    """Create Elasticsearch vector store with retrieval strategy.

    Based on: https://www.elastic.co/search-labs/blog/elasticsearch-llamaindex-ingest-data

    Args:
        index_name: Index name (default from env)
        es_url: Elasticsearch URL (default from env)
        strategy: Retrieval strategy: 'dense' | 'bm25' | 'sparse' | 'hybrid' (default from env)

    Returns:
        Configured ElasticsearchStore with strategy
    """
    index_name = index_name or os.getenv("ES_INDEX", "documents")
    es_url = es_url or os.getenv("ES_HOST", "http://localhost:9200")
    strategy = strategy or os.getenv("ELASTICSEARCH_STRATEGY", "hybrid")

    logger.info(f"Creating Elasticsearch store: {index_name} with strategy: {strategy}")

    # Import strategies
    try:
        from llama_index.vector_stores.elasticsearch import (
            AsyncBM25Strategy,
            AsyncDenseVectorStrategy,
            AsyncSparseVectorStrategy,
        )

        # Map strategy names to implementations
        strategy_map = {
            "dense": AsyncDenseVectorStrategy(),
            "bm25": AsyncBM25Strategy(),
            "sparse": AsyncSparseVectorStrategy(),
        }

        if strategy == "hybrid":
            # Hybrid uses both dense vectors and BM25
            retrieval_strategy = [
                AsyncDenseVectorStrategy(),
                AsyncBM25Strategy(),
            ]
            logger.info("Using hybrid strategy: Dense + BM25")
        elif strategy in strategy_map:
            retrieval_strategy = strategy_map[strategy]
            logger.info(f"Using single strategy: {strategy}")
        else:
            logger.warning(f"Unknown strategy '{strategy}', falling back to dense")
            retrieval_strategy = AsyncDenseVectorStrategy()

        return ElasticsearchStore(
            index_name=index_name,
            es_url=es_url,
            retrieval_strategy=retrieval_strategy,
        )

    except ImportError as e:
        logger.warning(f"Elasticsearch strategies not available: {e}, using basic store")
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
        embedder = embed_model or Settings.embed_model

        if embedder is None:
            api_key = os.getenv("OPENAI_API_KEY")
            model_name = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

            if api_key:
                embedder = OpenAIEmbedding(model=model_name, api_key=api_key)
            else:
                logger.error("No embedding model configured; skipping Qdrant indexing")
                return None

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
        embedder = embed_model or Settings.embed_model

        if embedder is None:
            api_key = os.getenv("OPENAI_API_KEY")
            model_name = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

            if api_key:
                embedder = OpenAIEmbedding(model=model_name, api_key=api_key)
            else:
                logger.error("No embedding model configured; skipping Elasticsearch indexing")
                return None

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
            # Use legal domain property graph. We return a count to keep
            # downstream tracker logic simple (they expect an integer).
            ingestor = LegalPropertyGraphIngestor()
            ingestor.ingest_nodes(nodes)
            return len(nodes)
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
