from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

from src.service.ingestion_service.llamaindex.indexer import index_nodes
from src.service.ingestion_service.loader.unstructured_loader import load_document_nodes
from src.service.ingestion_service.observability.stats_tracker import get_stats_tracker
from src.service.ingestion_service.progress_tracker import get_tracker
from src.service.ingestion_service.settings import GRAPH_MODE, WORKFLOW_ENABLE_VALIDATION

F = TypeVar("F", bound=Callable[..., Any])

LANGFUSE_AVAILABLE = False
_langfuse_observe: Optional[Callable[..., Callable[[F], F]]] = None
_langfuse_propagate: Optional[Callable[..., Any]] = None
_langfuse_get_client: Optional[Callable[[], Any]] = None

try:
    from langfuse import get_client as _get_client
    from langfuse import observe as _observe
    from langfuse import propagate_attributes as _propagate

    _test_client = _get_client()
    if _test_client and _test_client.auth_check():
        LANGFUSE_AVAILABLE = True
        _langfuse_observe = _observe
        _langfuse_propagate = _propagate
        _langfuse_get_client = _get_client
except ImportError:
    pass
except Exception:
    pass


def observe(name: Optional[str] = None, **kwargs: Any) -> Callable[[F], F]:
    if LANGFUSE_AVAILABLE and _langfuse_observe:
        return _langfuse_observe(name=name, **kwargs)

    def decorator(func: F) -> F:
        return func

    return decorator


class _NoOpContext:
    def __enter__(self) -> "_NoOpContext":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def propagate_attributes(**kwargs: Any) -> Any:
    if LANGFUSE_AVAILABLE and _langfuse_propagate:
        return _langfuse_propagate(**kwargs)
    return _NoOpContext()


def _update_langfuse_span(metadata: Optional[Dict[str, Any]] = None, level: Optional[str] = None) -> None:
    if LANGFUSE_AVAILABLE and _langfuse_get_client and metadata:
        try:
            client = _langfuse_get_client()
            if client:
                client.update_current_span(metadata=metadata, level=level)
        except Exception:
            pass


STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
DOCSTORE_PATH = STORAGE_DIR / "docstore.json"

_docstore: Optional[SimpleDocumentStore] = None


def _get_docstore() -> SimpleDocumentStore:
    global _docstore
    if _docstore is None:
        if DOCSTORE_PATH.exists():
            _docstore = SimpleDocumentStore.from_persist_path(str(DOCSTORE_PATH))
        else:
            _docstore = SimpleDocumentStore()
    return _docstore


def _persist_docstore() -> None:
    if _docstore is not None:
        _docstore.persist(str(DOCSTORE_PATH))


def _get_doc_hash(file_path: str) -> str:
    abs_path = os.path.abspath(file_path)
    return hashlib.md5(abs_path.encode()).hexdigest()


class NodesCreatedEvent(Event):
    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class ParsedNodesEvent(Event):
    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class ValidatedNodesEvent(Event):
    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]


class IndexedEvent(Event):
    nodes: List[BaseNode]
    file_path: str
    metadata: Dict[str, Any]
    results: Dict[str, Any]


class IngestionWorkflow(Workflow):
    def __init__(
        self,
        enable_qdrant: bool = True,
        enable_elasticsearch: bool = True,
        enable_neo4j: bool = True,
        timeout: int = 3600,
        return_nodes: bool = False,
        run_semantic_linking: bool = True,
        run_community_detection: bool = False,
        run_topic_extraction: bool = False,
        run_citation_linking: bool = False,
        run_temporal_linking: bool = False,
        run_entity_cooccurrence: bool = False,
        invalidate_cache: bool = False,
        **kwargs: Any,
    ):
        super().__init__(timeout=timeout, **kwargs)
        self.enable_qdrant = enable_qdrant
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_neo4j = enable_neo4j
        self.return_nodes = return_nodes
        self.run_semantic_linking = run_semantic_linking
        self.run_community_detection = run_community_detection
        self.run_topic_extraction = run_topic_extraction
        self.run_citation_linking = run_citation_linking
        self.run_temporal_linking = run_temporal_linking
        self.run_entity_cooccurrence = run_entity_cooccurrence
        self.invalidate_cache = invalidate_cache

    @observe(name="cache-lookup")
    def _get_cached_nodes(self, file_path: str) -> Optional[List[BaseNode]]:
        docstore = _get_docstore()
        doc_hash = _get_doc_hash(file_path)
        cached_nodes = []
        for node_id, node in docstore.docs.items():
            if node.metadata.get("_file_hash") == doc_hash:
                cached_nodes.append(node)
        if cached_nodes:
            cached_nodes.sort(key=lambda n: n.metadata.get("chunk_index", 0))
            _update_langfuse_span({"cache_hit": True, "nodes_found": len(cached_nodes)})
            return cached_nodes
        _update_langfuse_span({"cache_hit": False})
        return None

    @observe(name="cache-store")
    def _cache_nodes(self, file_path: str, nodes: List[BaseNode]) -> None:
        docstore = _get_docstore()
        doc_hash = _get_doc_hash(file_path)
        for node in nodes:
            node.metadata["_file_hash"] = doc_hash
        docstore.add_documents(nodes)
        _persist_docstore()
        _update_langfuse_span({"nodes_cached": len(nodes), "doc_hash": doc_hash})

    @observe(name="cache-invalidate")
    def _invalidate_cached_nodes(self, file_path: str) -> None:
        docstore = _get_docstore()
        doc_hash = _get_doc_hash(file_path)
        nodes_to_delete = [node_id for node_id, node in docstore.docs.items() if node.metadata.get("_file_hash") == doc_hash]
        for node_id in nodes_to_delete:
            docstore.delete_document(node_id)
        if nodes_to_delete:
            _persist_docstore()
        _update_langfuse_span({"nodes_invalidated": len(nodes_to_delete)})

    @step
    async def load_documents(self, ctx: Context, ev: StartEvent) -> NodesCreatedEvent | StopEvent:
        file_path = ev.get("file_path")
        metadata = ev.get("metadata", {})
        stats_tracker = get_stats_tracker()
        doc_id = metadata.get("doc_id") or metadata.get("id") or file_path

        if not file_path:
            stats_tracker.fail_document(str(doc_id), "loading", "No file_path provided")
            _update_langfuse_span({"error": "No file_path provided"}, level="ERROR")
            return StopEvent(result={"success": False, "error": "No file_path provided"})

        if self.invalidate_cache:
            self._invalidate_cached_nodes(file_path)

        cached_nodes = self._get_cached_nodes(file_path)
        if cached_nodes:
            return NodesCreatedEvent(nodes=cached_nodes, file_path=file_path, metadata=metadata)

        stats_tracker.start_document(str(doc_id), file_path, "loading")
        try:
            nodes, total_chunks, _ = _load_document_with_tracing(file_path, metadata)
        except Exception as exc:
            stats_tracker.fail_document(str(doc_id), "loading", str(exc))
            _update_langfuse_span({"error": str(exc), "stage": "loading"}, level="ERROR")
            return StopEvent(result={"success": False, "error": str(exc)})

        if not nodes:
            stats_tracker.fail_document(str(doc_id), "loading", "Loader returned no nodes")
            _update_langfuse_span({"error": "Loader returned no nodes"}, level="WARNING")
            return StopEvent(result={"success": False, "error": "Loader returned no nodes"})

        self._cache_nodes(file_path, nodes)
        return NodesCreatedEvent(nodes=nodes, file_path=file_path, metadata=metadata)

    @step
    async def parse_nodes(self, ctx: Context, ev: NodesCreatedEvent) -> ParsedNodesEvent:
        return ParsedNodesEvent(nodes=ev.nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def validate_nodes(self, ctx: Context, ev: ParsedNodesEvent) -> ValidatedNodesEvent:
        if not WORKFLOW_ENABLE_VALIDATION:
            return ValidatedNodesEvent(nodes=ev.nodes, file_path=ev.file_path, metadata=ev.metadata)
        valid_nodes = [n for n in ev.nodes if n.get_content().strip()]
        invalid_count = len(ev.nodes) - len(valid_nodes)
        if invalid_count > 0:
            _update_langfuse_span({"nodes_filtered": invalid_count}, level="WARNING")
        return ValidatedNodesEvent(nodes=valid_nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def index_all(self, ctx: Context, ev: ValidatedNodesEvent) -> IndexedEvent:
        nodes = ev.nodes

        if not nodes:
            return IndexedEvent(nodes=[], file_path=ev.file_path, metadata=ev.metadata, results={})

        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")
        doc_id = ev.metadata.get("doc_id") or ev.metadata.get("id")
        results = await _index_nodes_with_tracing(
            nodes,
            enable_qdrant=self.enable_qdrant,
            enable_elasticsearch=self.enable_elasticsearch,
            enable_neo4j=self.enable_neo4j and GRAPH_MODE != "off",
            upsert_doc_id=doc_id,
            run_semantic_linking=self.run_semantic_linking,
            run_community_detection=self.run_community_detection,
            run_topic_extraction=self.run_topic_extraction,
            run_citation_linking=self.run_citation_linking,
            run_temporal_linking=self.run_temporal_linking,
            run_entity_cooccurrence=self.run_entity_cooccurrence,
        )

        if self.enable_qdrant and not results.get("qdrant"):
            _update_langfuse_span({"error": "Qdrant indexing failed"}, level="ERROR")
            raise RuntimeError("Failed to index nodes to Qdrant")
        if self.enable_elasticsearch and not results.get("elasticsearch"):
            _update_langfuse_span({"error": "Elasticsearch indexing failed"}, level="ERROR")
            raise RuntimeError("Failed to index nodes to Elasticsearch")
        if self.enable_neo4j and not results.get("neo4j"):
            _update_langfuse_span({"error": "Neo4j indexing failed"}, level="ERROR")
            raise RuntimeError("Failed to index nodes to Neo4j")

        if results.get("qdrant"):
            tracker.track_phase_stats(file_type, "qdrant_uploaded", len(nodes))
        if results.get("elasticsearch"):
            tracker.track_phase_stats(file_type, "elasticsearch_uploaded", len(nodes))
        if results.get("neo4j"):
            tracker.track_phase_stats(file_type, "neo4j_uploaded", len(nodes))

        return IndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata, results=results)

    @step
    async def finalize(self, ctx: Context, ev: IndexedEvent) -> StopEvent:
        nodes = ev.nodes or []
        file_path = ev.file_path
        doc_id = ev.metadata.get("doc_id") or ev.metadata.get("id") or file_path
        stats_tracker = get_stats_tracker()

        stats_tracker.complete_document(str(doc_id), "complete")

        result: Dict[str, Any] = {
            "success": True,
            "file_path": file_path,
            "nodes_count": len(nodes),
            "message": f"Ingestion complete: {len(nodes)} nodes processed",
            "node_ids": [getattr(node, "node_id", None) or getattr(node, "id_", None) for node in nodes],
        }
        if self.return_nodes:
            result["nodes"] = nodes
        return StopEvent(result=result)


@observe(name="document-loading")
def _load_document_with_tracing(file_path: str, metadata: Dict[str, Any]) -> Any:
    nodes, total_chunks, doc_meta = load_document_nodes(file_path, metadata)
    _update_langfuse_span(
        {
            "total_chunks": total_chunks,
            "file_type": metadata.get("file_type", "unknown"),
            "file_path": file_path,
        }
    )
    return nodes, total_chunks, doc_meta


@observe(name="index-to-databases")
async def _index_nodes_with_tracing(
    nodes: List[BaseNode],
    enable_qdrant: bool = True,
    enable_elasticsearch: bool = True,
    enable_neo4j: bool = True,
    upsert_doc_id: Optional[str] = None,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
) -> Dict[str, Any]:
    _update_langfuse_span(
        {
            "nodes_count": len(nodes),
            "targets": {
                "qdrant": enable_qdrant,
                "elasticsearch": enable_elasticsearch,
                "neo4j": enable_neo4j,
            },
            "graph_operations": {
                "semantic_linking": run_semantic_linking,
                "community_detection": run_community_detection,
                "topic_extraction": run_topic_extraction,
            },
        }
    )
    results = await index_nodes(
        nodes,
        enable_qdrant=enable_qdrant,
        enable_elasticsearch=enable_elasticsearch,
        enable_neo4j=enable_neo4j,
        upsert_doc_id=upsert_doc_id,
        run_semantic_linking=run_semantic_linking,
        run_community_detection=run_community_detection,
        run_topic_extraction=run_topic_extraction,
        run_citation_linking=run_citation_linking,
        run_temporal_linking=run_temporal_linking,
        run_entity_cooccurrence=run_entity_cooccurrence,
    )
    _update_langfuse_span({"index_results": results})
    return results


@observe(name="ingestion-workflow")
async def run_ingestion_workflow(
    file_path: str,
    metadata: Optional[Dict[str, Any]] = None,
    return_nodes: bool = False,
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    invalidate_cache: bool = False,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    if "return_nodes" in kwargs:
        return_nodes = bool(kwargs.pop("return_nodes"))

    doc_id = (metadata or {}).get("doc_id") or (metadata or {}).get("id") or file_path
    file_type = (metadata or {}).get("file_type", "document")

    with propagate_attributes(
        user_id=user_id,
        session_id=session_id,
        metadata={
            "doc_id": str(doc_id),
            "file_type": file_type,
            "file_path": file_path,
        },
        tags=["ingestion", file_type],
    ):
        workflow = IngestionWorkflow(
            return_nodes=return_nodes,
            run_semantic_linking=run_semantic_linking,
            run_community_detection=run_community_detection,
            run_topic_extraction=run_topic_extraction,
            run_citation_linking=run_citation_linking,
            run_temporal_linking=run_temporal_linking,
            run_entity_cooccurrence=run_entity_cooccurrence,
            invalidate_cache=invalidate_cache,
            **kwargs,
        )
        result = await workflow.run(
            file_path=file_path,
            metadata=metadata or {},
        )
        return result
