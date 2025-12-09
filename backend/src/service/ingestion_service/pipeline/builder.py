"""
IngestionPipelineBuilder - Fluent builder for modular pipeline construction.

This replaces ad-hoc pipeline creation with a declarative, chainable API.
Supports all LlamaIndex ingestion features:
- Chunking (SentenceSplitter, SemanticSplitter)
- Metadata extraction
- Custom transformations
- Caching (IngestionCache)
- Deduplication (SimpleDocumentStore + DocstoreStrategy)
- Embeddings
- Pipeline persistence
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Union

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TransformComponent

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
IngestionCache = None
SimpleDocumentStore = None
DocstoreStrategy = None


def _ensure_cache_imports():
    """Lazily import caching components."""
    global IngestionCache
    if IngestionCache is None:
        try:
            from llama_index.core.ingestion import IngestionCache as _IC

            IngestionCache = _IC
        except ImportError:
            logger.warning("IngestionCache not available")
            IngestionCache = False


def _ensure_docstore_imports():
    """Lazily import docstore components."""
    global SimpleDocumentStore, DocstoreStrategy
    if SimpleDocumentStore is None:
        try:
            from llama_index.core.storage.docstore import SimpleDocumentStore as _SDS

            SimpleDocumentStore = _SDS
        except ImportError:
            logger.warning("SimpleDocumentStore not available")
            SimpleDocumentStore = False

    if DocstoreStrategy is None:
        try:
            from llama_index.core.ingestion import DocstoreStrategy as _DS

            DocstoreStrategy = _DS
        except ImportError:
            logger.warning("DocstoreStrategy not available")
            DocstoreStrategy = False


class IngestionPipelineBuilder:
    """
    Fluent builder for constructing modular ingestion pipelines.

    Example:
        pipeline = (
            IngestionPipelineBuilder()
            .with_chunking(chunk_size=512)
            .with_transform(ContextualNodeParser())
            .with_transform(GraphRAGExtractor())
            .with_deduplication(strategy="upserts_and_delete")
            .with_caching()
            .with_embeddings()
            .build()
        )

        nodes = pipeline.run(documents, num_workers=4)
        pipeline.persist("./cache")
    """

    def __init__(self):
        self._transformations: List[TransformComponent] = []
        self._docstore = None
        self._docstore_strategy: Optional[str] = None
        self._cache = None
        self._vector_store = None
        self._persist_dir: Optional[Path] = None

    def with_chunking(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        paragraph_separator: str = "\n\n",
    ) -> "IngestionPipelineBuilder":
        """
        Add sentence-aware chunking as first transformation.

        Args:
            chunk_size: Max chunk size (default: Settings.chunk_size or 1024)
            chunk_overlap: Overlap between chunks (default: Settings.chunk_overlap or 200)
            paragraph_separator: Separator for paragraph detection

        Returns:
            self for chaining
        """
        _chunk_size = chunk_size if chunk_size is not None else getattr(Settings, "chunk_size", 1024)
        _chunk_overlap = chunk_overlap if chunk_overlap is not None else getattr(Settings, "chunk_overlap", 200)
        splitter = SentenceSplitter(
            chunk_size=int(_chunk_size) if _chunk_size is not None else 1024,
            chunk_overlap=int(_chunk_overlap) if _chunk_overlap is not None else 200,
            paragraph_separator=paragraph_separator,
        )
        self._transformations.append(splitter)
        logger.debug(f"Added SentenceSplitter (size={_chunk_size}, overlap={_chunk_overlap})")
        return self

    def with_transform(self, transform: TransformComponent) -> "IngestionPipelineBuilder":
        """
        Add any TransformComponent to the pipeline.

        Use this for:
        - ContextualNodeParser
        - GraphRAGExtractor
        - Metadata extractors (TitleExtractor, KeywordsExtractor, etc.)
        - Custom TransformComponent subclasses

        Args:
            transform: Any TransformComponent instance

        Returns:
            self for chaining
        """
        self._transformations.append(transform)
        class_name = getattr(transform, "class_name", lambda: type(transform).__name__)
        logger.debug(f"Added transform: {class_name() if callable(class_name) else class_name}")
        return self

    def with_embeddings(self, embed_model: Optional[Any] = None) -> "IngestionPipelineBuilder":
        """
        Add embedding generation as final transformation.

        Args:
            embed_model: Embedding model (default: Settings.embed_model)

        Returns:
            self for chaining
        """
        model = embed_model or Settings.embed_model
        self._transformations.append(model)
        logger.debug("Added embedding model as final transform")
        return self

    def with_deduplication(
        self,
        strategy: str = "upserts",
        persist_dir: Optional[Union[str, Path]] = None,
    ) -> "IngestionPipelineBuilder":
        """
        Enable document deduplication with SimpleDocumentStore.

        Strategies:
        - "duplicates_only": Skip if doc_id hash unchanged
        - "upserts": Update if changed, insert if new
        - "upserts_and_delete": Also delete removed docs (requires vector_store)

        Args:
            strategy: Deduplication strategy name
            persist_dir: Optional directory to persist docstore

        Returns:
            self for chaining
        """
        _ensure_docstore_imports()

        if SimpleDocumentStore is False:
            logger.warning("SimpleDocumentStore not available, skipping deduplication")
            return self

        # Create or load docstore
        # At this point, SimpleDocumentStore is a class (not None or False)
        assert SimpleDocumentStore is not None and SimpleDocumentStore is not False
        if persist_dir:
            persist_path = Path(persist_dir)
            docstore_path = persist_path / "docstore.json"
            if docstore_path.exists():
                try:
                    self._docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
                    logger.info(f"Loaded existing docstore from {docstore_path}")
                except Exception as e:
                    logger.warning(f"Failed to load docstore: {e}, creating new")
                    self._docstore = SimpleDocumentStore()
            else:
                self._docstore = SimpleDocumentStore()
            self._persist_dir = persist_path
        else:
            self._docstore = SimpleDocumentStore()

        # Set strategy
        if DocstoreStrategy is not None and DocstoreStrategy is not False:
            strategy_map = {
                "duplicates_only": DocstoreStrategy.DUPLICATES_ONLY,
                "upserts": DocstoreStrategy.UPSERTS,
                "upserts_and_delete": DocstoreStrategy.UPSERTS_AND_DELETE,
            }
            self._docstore_strategy = strategy_map.get(strategy.lower())
            if self._docstore_strategy is None:
                logger.warning(f"Unknown strategy '{strategy}', using 'upserts'")
                self._docstore_strategy = DocstoreStrategy.UPSERTS

        logger.debug(f"Enabled deduplication with strategy={strategy}")
        return self

    def with_caching(
        self,
        persist_dir: Optional[Union[str, Path]] = None,
    ) -> "IngestionPipelineBuilder":
        """
        Enable transform caching with IngestionCache.

        Caches the output of each (node, transform) pair to skip
        repeated computations on unchanged data.

        Args:
            persist_dir: Optional directory to persist cache

        Returns:
            self for chaining
        """
        _ensure_cache_imports()

        if IngestionCache is None or IngestionCache is False:
            logger.warning("IngestionCache not available, skipping caching")
            return self

        # At this point, IngestionCache is a class (not None or False)
        self._cache = IngestionCache()

        if persist_dir:
            self._persist_dir = Path(persist_dir)

        logger.debug("Enabled transform caching")
        return self

    def with_vector_store(self, vector_store: Any) -> "IngestionPipelineBuilder":
        """
        Attach vector store for direct node insertion.

        When a vector_store is attached:
        - Nodes are automatically inserted after processing
        - Works with DocstoreStrategy.UPSERTS_AND_DELETE

        Args:
            vector_store: Any LlamaIndex vector store (Qdrant, Pinecone, etc.)

        Returns:
            self for chaining
        """
        self._vector_store = vector_store
        logger.debug("Attached vector store for direct insertion")
        return self

    def build(self) -> IngestionPipeline:
        """
        Build the configured IngestionPipeline.

        Returns:
            Configured IngestionPipeline ready for .run() or .arun()
        """
        if not self._transformations:
            logger.warning("No transformations configured, pipeline will be minimal")

        kwargs: dict = {
            "transformations": self._transformations,
        }

        if self._docstore:
            kwargs["docstore"] = self._docstore

        if self._docstore_strategy:
            kwargs["docstore_strategy"] = self._docstore_strategy

        if self._cache:
            kwargs["cache"] = self._cache

        if self._vector_store:
            kwargs["vector_store"] = self._vector_store

        pipeline = IngestionPipeline(**kwargs)

        logger.info(f"Built IngestionPipeline with {len(self._transformations)} transforms, " f"docstore={'yes' if self._docstore else 'no'}, " f"cache={'yes' if self._cache else 'no'}")

        return pipeline

    def persist_state(self, pipeline: IngestionPipeline, persist_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Persist pipeline state (docstore, cache) to disk.

        Args:
            pipeline: The pipeline to persist
            persist_dir: Directory to save state (default: configured persist_dir)
        """
        save_dir = Path(persist_dir) if persist_dir else self._persist_dir
        if not save_dir:
            logger.warning("No persist_dir configured, skipping persistence")
            return

        save_dir.mkdir(parents=True, exist_ok=True)

        # Persist docstore
        if self._docstore:
            docstore_path = save_dir / "docstore.json"
            self._docstore.persist(str(docstore_path))
            logger.info(f"Persisted docstore to {docstore_path}")

        # Persist pipeline cache
        try:
            pipeline.persist(str(save_dir))
            logger.info(f"Persisted pipeline cache to {save_dir}")
        except Exception as e:
            logger.warning(f"Failed to persist pipeline: {e}")

    @classmethod
    def load_from_persist_dir(cls, persist_dir: Union[str, Path]) -> IngestionPipeline:
        """
        Load a persisted pipeline.

        Args:
            persist_dir: Directory where pipeline was saved

        Returns:
            Loaded IngestionPipeline
        """
        try:
            # Create pipeline and load state in-place
            pipeline = IngestionPipeline(transformations=[])
            pipeline.load(str(persist_dir))  # type: ignore[arg-type]
            logger.info(f"Loaded pipeline from {persist_dir}")
            return pipeline
        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            raise
