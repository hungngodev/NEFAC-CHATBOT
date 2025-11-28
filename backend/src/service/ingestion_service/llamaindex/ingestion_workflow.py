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

from src.service.ingestion_service.llamaindex.indexer import index_nodes
from src.service.ingestion_service.loader.unstructured_loader import load_document_nodes
from src.service.ingestion_service.progress_tracker import get_tracker
from src.service.ingestion_service.settings import GRAPH_MODE, WORKFLOW_ENABLE_VALIDATION

logger = logging.getLogger(__name__)


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
        **kwargs,
    ):
        super().__init__(timeout=timeout, **kwargs)
        self.enable_qdrant = enable_qdrant
        self.enable_elasticsearch = enable_elasticsearch
        self.enable_neo4j = enable_neo4j
        self.return_nodes = return_nodes

    @step
    async def load_documents(self, ctx: Context, ev: StartEvent) -> NodesCreatedEvent | StopEvent:
        file_path = ev.get("file_path")
        metadata = ev.get("metadata", {})
        if not file_path:
            return StopEvent(result={"success": False, "error": "No file_path provided"})
        logger.info(f"[Workflow] Loading document via unstructured loader: {file_path}")
        try:
            nodes, total_chunks, _ = load_document_nodes(file_path, metadata)
        except Exception as exc:
            logger.error("[Workflow] Failed to load document %s: %s", file_path, exc)
            return StopEvent(result={"success": False, "error": str(exc)})
        if not nodes:
            return StopEvent(result={"success": False, "error": "Loader returned no nodes"})
        logger.info("[Workflow] Loader produced %d nodes", len(nodes))
        return NodesCreatedEvent(nodes=nodes, file_path=file_path, metadata=metadata)

    @step
    async def parse_nodes(self, ctx: Context, ev: NodesCreatedEvent) -> ParsedNodesEvent:
        step_start = time.perf_counter()
        file_path = ev.file_path
        node_count = len(ev.nodes)
        logger.info("[Workflow] Entering parse step for %s (%d nodes)", file_path, node_count)
        sample_ids = []
        for node in ev.nodes[:3]:
            meta = getattr(node, "metadata", {}) or {}
            sample_ids.append(meta.get("chunk_id") or meta.get("id") or getattr(node, "node_id", None))
        logger.info("[Workflow] Parsed nodes sample ids: %s", sample_ids)
        logger.info(
            "[Workflow] Parse step finished in %.2fs",
            time.perf_counter() - step_start,
        )
        return ParsedNodesEvent(nodes=ev.nodes, file_path=ev.file_path, metadata=ev.metadata)

    @step
    async def validate_nodes(self, ctx: Context, ev: ParsedNodesEvent) -> ValidatedNodesEvent:
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
    async def index_all(self, ctx: Context, ev: ValidatedNodesEvent) -> IndexedEvent:
        nodes = ev.nodes
        step_start = time.perf_counter()
        logger.info(
            "[Workflow] Indexing %d nodes (qdrant=%s, es=%s, neo4j=%s)",
            len(nodes),
            self.enable_qdrant,
            self.enable_elasticsearch,
            self.enable_neo4j,
        )
        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")
        doc_id = ev.metadata.get("doc_id") or ev.metadata.get("id")
        results = index_nodes(
            nodes,
            enable_qdrant=self.enable_qdrant,
            enable_elasticsearch=self.enable_elasticsearch,
            enable_neo4j=self.enable_neo4j and GRAPH_MODE != "off",
            upsert_doc_id=doc_id,
        )
        if results.get("qdrant"):
            tracker.track_phase_stats(file_type, "qdrant_uploaded", len(nodes))
        if results.get("elasticsearch"):
            tracker.track_phase_stats(file_type, "elasticsearch_uploaded", len(nodes))
        if results.get("neo4j"):
            tracker.track_phase_stats(file_type, "neo4j_uploaded", len(nodes))
        logger.info(
            "[Workflow] Indexing step finished in %.2fs",
            time.perf_counter() - step_start,
        )
        return IndexedEvent(nodes=nodes, file_path=ev.file_path, metadata=ev.metadata, results=results)

    @step
    async def finalize(self, ctx: Context, ev: IndexedEvent) -> StopEvent:
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


async def run_ingestion_workflow(
    file_path: str,
    metadata: Optional[Dict[str, Any]] = None,
    return_nodes: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    if "return_nodes" in kwargs:
        return_nodes = bool(kwargs.pop("return_nodes"))
    workflow = IngestionWorkflow(return_nodes=return_nodes, **kwargs)
    result = await workflow.run(
        file_path=file_path,
        metadata=metadata or {},
    )
    return result
