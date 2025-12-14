from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Union

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TransformComponent

IngestionCache = None
SimpleDocumentStore = None
DocstoreStrategy = None


def _ensure_cache_imports():
    global IngestionCache
    if IngestionCache is None:
        try:
            from llama_index.core.ingestion import IngestionCache as _IC

            IngestionCache = _IC
        except ImportError:
            IngestionCache = False


def _ensure_docstore_imports():
    global SimpleDocumentStore, DocstoreStrategy
    if SimpleDocumentStore is None:
        try:
            from llama_index.core.storage.docstore import SimpleDocumentStore as _SDS

            SimpleDocumentStore = _SDS
        except ImportError:
            SimpleDocumentStore = False

    if DocstoreStrategy is None:
        try:
            from llama_index.core.ingestion import DocstoreStrategy as _DS

            DocstoreStrategy = _DS
        except ImportError:
            DocstoreStrategy = False


class IngestionPipelineBuilder:
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
        _chunk_size = chunk_size if chunk_size is not None else getattr(Settings, "chunk_size", 1024)
        _chunk_overlap = chunk_overlap if chunk_overlap is not None else getattr(Settings, "chunk_overlap", 200)
        splitter = SentenceSplitter(
            chunk_size=int(_chunk_size) if _chunk_size is not None else 1024,
            chunk_overlap=int(_chunk_overlap) if _chunk_overlap is not None else 200,
            paragraph_separator=paragraph_separator,
        )
        self._transformations.append(splitter)
        return self

    def with_transform(self, transform: TransformComponent) -> "IngestionPipelineBuilder":
        self._transformations.append(transform)
        return self

    def with_embeddings(self, embed_model: Optional[Any] = None) -> "IngestionPipelineBuilder":
        model = embed_model or Settings.embed_model
        self._transformations.append(model)
        return self

    def with_deduplication(
        self,
        strategy: str = "upserts",
        persist_dir: Optional[Union[str, Path]] = None,
    ) -> "IngestionPipelineBuilder":
        _ensure_docstore_imports()

        if SimpleDocumentStore is False:
            return self

        assert SimpleDocumentStore is not None and SimpleDocumentStore is not False
        if persist_dir:
            persist_path = Path(persist_dir)
            docstore_path = persist_path / "docstore.json"
            if docstore_path.exists():
                try:
                    self._docstore = SimpleDocumentStore.from_persist_path(str(docstore_path))
                except Exception:
                    self._docstore = SimpleDocumentStore()
            else:
                self._docstore = SimpleDocumentStore()
            self._persist_dir = persist_path
        else:
            self._docstore = SimpleDocumentStore()

        if DocstoreStrategy is not None and DocstoreStrategy is not False:
            strategy_map = {
                "duplicates_only": DocstoreStrategy.DUPLICATES_ONLY,
                "upserts": DocstoreStrategy.UPSERTS,
                "upserts_and_delete": DocstoreStrategy.UPSERTS_AND_DELETE,
            }
            self._docstore_strategy = strategy_map.get(strategy.lower(), DocstoreStrategy.UPSERTS)

        return self

    def with_caching(
        self,
        persist_dir: Optional[Union[str, Path]] = None,
    ) -> "IngestionPipelineBuilder":
        _ensure_cache_imports()

        if IngestionCache is None or IngestionCache is False:
            return self

        self._cache = IngestionCache()

        if persist_dir:
            self._persist_dir = Path(persist_dir)

        return self

    def with_vector_store(self, vector_store: Any) -> "IngestionPipelineBuilder":
        self._vector_store = vector_store
        return self

    def build(self) -> IngestionPipeline:
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

        return IngestionPipeline(**kwargs)

    def persist_state(self, pipeline: IngestionPipeline, persist_dir: Optional[Union[str, Path]] = None) -> None:
        save_dir = Path(persist_dir) if persist_dir else self._persist_dir
        if not save_dir:
            return

        save_dir.mkdir(parents=True, exist_ok=True)

        if self._docstore:
            docstore_path = save_dir / "docstore.json"
            self._docstore.persist(str(docstore_path))

        try:
            pipeline.persist(str(save_dir))
        except Exception:
            pass

    @classmethod
    def load_from_persist_dir(cls, persist_dir: Union[str, Path]) -> IngestionPipeline:
        pipeline = IngestionPipeline(transformations=[])
        pipeline.load(str(persist_dir))  # type: ignore[arg-type]
        return pipeline
