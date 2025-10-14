"""Hybrid retriever combining dense, sparse, and knowledge graph retrieval.

Based on: https://developers.llamaindex.ai/python/examples/retrievers/multi_doc_together_hybrid/
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import BaseRetriever, VectorIndexRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining multiple retrieval strategies.
    
    Features:
    - Dense vector search (semantic similarity)
    - Sparse keyword search (BM25)
    - Knowledge graph traversal (optional)
    - Reciprocal Rank Fusion (RRF)
    - Reranking with Cohere
    
    Usage:
        >>> vector_index = VectorStoreIndex.from_documents(docs)
        >>> retriever = HybridRetriever(
        ...     vector_index=vector_index,
        ...     enable_bm25=True,
        ...     enable_rerank=True,
        ...     top_k=10,
        ...     rerank_top_n=5
        ... )
        >>> results = retriever.retrieve("What are NEFAC's guidelines?")
    """
    
    def __init__(
        self,
        vector_index: VectorStoreIndex,
        enable_bm25: bool = True,
        enable_graph: bool = False,
        enable_rerank: bool = True,
        top_k: int = 10,
        rerank_top_n: int = 5,
        rerank_model: str = "rerank-english-v3.0",
        graph_query_fn: Optional[Callable[[QueryBundle], List[NodeWithScore]]] = None,
        fusion_strategy: str = "rrf",
        weights: Optional[Dict[str, float]] = None,
        rrf_k: float = 60.0,
        min_score: float = 0.0,
    ):
        """Initialize hybrid retriever.
        
        Args:
            vector_index: Vector store index for dense retrieval
            enable_bm25: Enable BM25 sparse retrieval
            enable_graph: Enable knowledge graph traversal
            enable_rerank: Enable Cohere reranking
            top_k: Number of results before reranking
            rerank_top_n: Number of results after reranking
            rerank_model: Cohere reranker model name
        """
        self.vector_index = vector_index
        self.enable_bm25 = enable_bm25
        self.enable_graph = enable_graph
        self.enable_rerank = enable_rerank
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.rerank_model = rerank_model
        self.graph_query_fn = graph_query_fn

        weight_config = weights or {}
        self.weights = {
            "dense": float(os.getenv("HYBRID_DENSE_WEIGHT", weight_config.get("dense", 1.0))),
            "sparse": float(os.getenv("HYBRID_SPARSE_WEIGHT", weight_config.get("sparse", 0.75))),
            "graph": float(os.getenv("HYBRID_GRAPH_WEIGHT", weight_config.get("graph", 0.5))),
        }

        self.fusion_strategy = (os.getenv("HYBRID_FUSION_STRATEGY", fusion_strategy) or "rrf").lower()
        self.rrf_k = float(os.getenv("HYBRID_RRF_K", rrf_k))
        self.min_score = float(os.getenv("HYBRID_MIN_SCORE", min_score))

        self._setup_retrievers()
        
        super().__init__()
    
    def _setup_retrievers(self):
        """Setup individual retrievers and fusion."""
        self._retrievers: Dict[str, VectorIndexRetriever] = {}

        # 1. Dense vector retriever (always enabled)
        self.vector_retriever = VectorIndexRetriever(
            index=self.vector_index,
            similarity_top_k=self.top_k,
        )
        self._retrievers["dense"] = self.vector_retriever
        logger.info("Dense vector retriever enabled")
        
        # 2. BM25 sparse retriever (if enabled)
        if self.enable_bm25:
            try:
                from llama_index.retrievers.bm25 import BM25Retriever  # type: ignore[import]
                import Stemmer  # type: ignore[import]
                
                # Get all nodes from index
                nodes = list(self.vector_index.docstore.docs.values())
                
                self.bm25_retriever = BM25Retriever.from_defaults(
                    nodes=nodes,
                    similarity_top_k=self.top_k,
                    stemmer=Stemmer.Stemmer("english"),
                    language="english",
                )
                self._retrievers["sparse"] = self.bm25_retriever
                logger.info("BM25 sparse retriever enabled")
            except ImportError as e:
                logger.warning(f"BM25Retriever not available: {e}")
                self.enable_bm25 = False
        
        # 4. Reranker (if enabled)
        if self.enable_rerank:
            try:
                from llama_index.postprocessor.cohere_rerank import CohereRerank  # type: ignore[import]
                
                cohere_api_key = os.getenv("COHERE_API_KEY")
                if not cohere_api_key:
                    logger.warning("COHERE_API_KEY not set, reranking disabled")
                    self.enable_rerank = False
                else:
                    self.reranker = CohereRerank(
                        api_key=cohere_api_key,
                        top_n=self.rerank_top_n,
                        model=self.rerank_model,
                    )
                    logger.info(f"Cohere reranker enabled with model: {self.rerank_model}")
            except ImportError as e:
                logger.warning(f"CohereRerank not available: {e}")
                self.enable_rerank = False
    
    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve nodes using hybrid approach.
        
        Args:
            query_bundle: Query bundle with query string
            
        Returns:
            List of nodes with scores
        """
        # Step 1: Run individual retrievers
        channel_results: Dict[str, List[NodeWithScore]] = {}
        dense_nodes = self.vector_retriever.retrieve(query_bundle)
        channel_results["dense"] = dense_nodes

        if self.enable_bm25 and hasattr(self, "bm25_retriever"):
            try:
                channel_results["sparse"] = self.bm25_retriever.retrieve(query_bundle)
            except Exception as exc:
                logger.warning("BM25 retrieval failed: %s", exc)

        graph_nodes: List[NodeWithScore] = []
        if self.enable_graph and self.graph_query_fn is not None:
            try:
                graph_nodes = self.graph_query_fn(query_bundle)
                channel_results["graph"] = graph_nodes
                logger.debug("Retrieved %d nodes from graph retriever", len(graph_nodes))
            except Exception as exc:
                logger.warning("Graph retrieval failed: %s", exc)
        
        fused_nodes = self._fuse_nodes(channel_results)
        logger.debug("Retrieved %d fused nodes before reranking", len(fused_nodes))

        # Step 2: Rerank if enabled
        if self.enable_rerank and hasattr(self, "reranker"):
            try:
                fused_nodes = self.reranker.postprocess_nodes(
                    fused_nodes,
                    query_bundle=query_bundle,
                )
                logger.debug(f"Reranked to {len(fused_nodes)} nodes")
            except Exception as e:
                logger.warning(f"Reranking failed: {e}, using pre-rerank results")

        limited = fused_nodes[: self.rerank_top_n or self.top_k]
        logger.info("Retrieved %d nodes for query: '%s...'", len(limited), query_bundle.query_str[:50])

        return limited
    
    def retrieve(self, str_or_query_bundle: str | QueryBundle) -> List[NodeWithScore]:
        """Public retrieve method (required by BaseRetriever).
        
        Args:
            str_or_query_bundle: Query string or QueryBundle
            
        Returns:
            List of nodes with scores
        """
        if isinstance(str_or_query_bundle, str):
            query_bundle = QueryBundle(query_str=str_or_query_bundle)
        else:
            query_bundle = str_or_query_bundle
        
        return self._retrieve(query_bundle)

    def _fuse_nodes(self, channel_results: Dict[str, List[NodeWithScore]]) -> List[NodeWithScore]:
        """Fuse nodes from multiple retrievers using configured strategy."""

        if not channel_results:
            return []

        aggregate_scores: Dict[str, float] = defaultdict(float)
        exemplars: Dict[str, NodeWithScore] = {}

        for channel, nodes in channel_results.items():
            if not nodes:
                continue

            weight = self.weights.get(channel, 0.0)
            if weight <= 0:
                continue

            for rank, node in enumerate(nodes, start=1):
                base_score = node.score or 0.0
                key = getattr(node.node, "node_id", None) or getattr(node.node, "id_", None) or str(hash(node.node.get_content()))

                if self.fusion_strategy == "score":
                    contribution = weight * base_score
                else:  # default to reciprocal rank fusion
                    contribution = weight * (1.0 / (self.rrf_k + rank))

                aggregate_scores[key] += contribution
                # Preserve highest raw score exemplar for metadata/relationships
                if key not in exemplars or (node.score or 0.0) > (exemplars[key].score or 0.0):
                    exemplars[key] = node

        fused = [
            NodeWithScore(node=exemplars[key].node, score=score)
            for key, score in aggregate_scores.items()
            if score >= self.min_score
        ]

        fused.sort(key=lambda n: n.score or 0.0, reverse=True)

        # Limit to requested top_k before rerank stage
        return fused[: self.top_k]


class MultiDocHybridRetriever(HybridRetriever):
    """Extended hybrid retriever with document-level signals.
    
    Combines chunk-level and document-level retrieval for better ranking.
    Based on: https://developers.llamaindex.ai/python/examples/retrievers/multi_doc_together_hybrid/
    """
    
    def __init__(
        self,
        vector_index: VectorStoreIndex,
        doc_vector_index: Optional[VectorStoreIndex] = None,
        doc_weight: float = 0.3,
        chunk_weight: float = 0.7,
        **kwargs
    ):
        """Initialize multi-doc hybrid retriever.
        
        Args:
            vector_index: Chunk-level vector index
            doc_vector_index: Document-level vector index (optional)
            doc_weight: Weight for document-level scores
            chunk_weight: Weight for chunk-level scores
            **kwargs: Additional arguments for HybridRetriever
        """
        super().__init__(vector_index=vector_index, **kwargs)
        
        self.doc_vector_index = doc_vector_index
        self.doc_weight = doc_weight
        self.chunk_weight = chunk_weight
        
        if doc_vector_index:
            self.doc_retriever = VectorIndexRetriever(
                index=doc_vector_index,
                similarity_top_k=10,  # Retrieve more docs
            )
            logger.info("Document-level retriever enabled")
    
    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve with document-level boosting.
        
        Args:
            query_bundle: Query bundle
            
        Returns:
            List of nodes with boosted scores
        """
        # Get chunk-level results
        chunk_nodes = super()._retrieve(query_bundle)
        
        # If no document index, return chunk results
        if not self.doc_vector_index or not hasattr(self, 'doc_retriever'):
            return chunk_nodes
        
        try:
            # Get document-level results
            doc_nodes = self.doc_retriever.retrieve(query_bundle)
            
            # Build document score map
            doc_scores = {}
            for node in doc_nodes:
                doc_id = node.metadata.get("document_id") or node.metadata.get("file_name")
                if doc_id:
                    doc_scores[doc_id] = node.score or 0.0
            
            # Boost chunk scores based on document scores
            boosted_nodes = []
            for node in chunk_nodes:
                doc_id = node.metadata.get("document_id") or node.metadata.get("file_name")
                doc_score = doc_scores.get(doc_id, 0.0)
                
                # Combine scores with weights
                chunk_score = node.score or 0.0
                combined_score = (self.chunk_weight * chunk_score) + (self.doc_weight * doc_score)
                
                # Create new node with boosted score
                boosted_node = NodeWithScore(node=node.node, score=combined_score)
                boosted_nodes.append(boosted_node)
            
            # Re-sort by combined score
            boosted_nodes.sort(key=lambda x: x.score or 0.0, reverse=True)
            
            logger.info("Applied document-level boosting to chunk scores")
            return boosted_nodes[:self.rerank_top_n]
        
        except Exception as e:
            logger.warning(f"Document-level boosting failed: {e}, using chunk-only results")
            return chunk_nodes


# Convenience function
def create_hybrid_retriever(
    vector_index: VectorStoreIndex,
    mode: str = "hybrid",
    **kwargs
) -> BaseRetriever:
    """Create a hybrid retriever with the specified mode.
    
    Args:
        vector_index: Vector store index
        mode: Retrieval mode - "hybrid", "multi_doc", or "vector_only"
        **kwargs: Additional retriever arguments
        
    Returns:
        Configured retriever instance
    """
    
    if mode == "multi_doc":
        return MultiDocHybridRetriever(vector_index=vector_index, **kwargs)
    elif mode == "hybrid":
        return HybridRetriever(vector_index=vector_index, **kwargs)
    elif mode == "vector_only":
        return VectorIndexRetriever(index=vector_index, similarity_top_k=kwargs.get("top_k", 10))
    else:
        raise ValueError(f"Unknown retriever mode: {mode}")
