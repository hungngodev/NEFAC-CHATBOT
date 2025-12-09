from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index.core.schema import BaseNode, TextNode
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

CACHE_DIR = Path(__file__).parent.parent / "cache" / "nodes"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


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
        **kwargs,
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
        logger.info(f"DEBUG: IngestionWorkflow initialized with invalidate_cache={self.invalidate_cache}")

    def _get_cache_path(self, file_path: str) -> Path:
        abs_path = os.path.abspath(file_path)
        file_hash = hashlib.md5(abs_path.encode()).hexdigest()
        return CACHE_DIR / f"{file_hash}.json"

    @step
    async def load_documents(self, ctx: Context, ev: StartEvent) -> NodesCreatedEvent | StopEvent:
        file_path = ev.get("file_path")
        metadata = ev.get("metadata", {})
        if not file_path:
            return StopEvent(result={"success": False, "error": "No file_path provided"})

        cache_path = self._get_cache_path(file_path)

        # Invalidate cache if requested
        if self.invalidate_cache and cache_path.exists():
            try:
                logger.info(f"[Workflow] Invalidating cache for {file_path}")
                cache_path.unlink()
            except Exception as e:
                logger.warning(f"[Workflow] Failed to delete cache file {cache_path}: {e}")

        # Try loading from cache
        if cache_path.exists():
            try:
                source_mtime = os.path.getmtime(file_path)
                cache_mtime = cache_path.stat().st_mtime
                if cache_mtime > source_mtime:
                    logger.info(f"[Workflow] Loading nodes from cache: {cache_path}")
                    with open(cache_path, "r") as f:
                        data = json.load(f)
                    # Deserialize nodes (assuming TextNode for now as per loader)
                    nodes = [TextNode.from_dict(n) for n in data["nodes"]]
                    logger.info("[Workflow] Loaded %d nodes from cache", len(nodes))
                    return NodesCreatedEvent(nodes=nodes, file_path=file_path, metadata=metadata)  # type: ignore[arg-type]
                else:
                    logger.info(f"[Workflow] Cache expired for {file_path}")
            except Exception as e:
                logger.warning(f"[Workflow] Failed to load cache: {e}")

        logger.info(f"[Workflow] Loading document via unstructured loader: {file_path}")
        try:
            nodes, total_chunks, _ = load_document_nodes(file_path, metadata)
        except Exception as exc:
            logger.error("[Workflow] Failed to load document %s: %s", file_path, exc)
            return StopEvent(result={"success": False, "error": str(exc)})
        if not nodes:
            return StopEvent(result={"success": False, "error": "Loader returned no nodes"})

        # Save to cache
        try:
            cache_data = {
                "nodes": [n.to_dict() for n in nodes],
                "total_chunks": total_chunks,
            }
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)
            logger.info(f"[Workflow] Saved nodes to cache: {cache_path}")
        except Exception as e:
            logger.warning(f"[Workflow] Failed to save cache: {e}")

        logger.info("[Workflow] Loader produced %d nodes", len(nodes))
        return NodesCreatedEvent(nodes=nodes, file_path=file_path, metadata=metadata)  # type: ignore[arg-type]

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

        if not nodes:
            logger.warning("[Workflow] No valid nodes to index for %s", ev.file_path)
            return IndexedEvent(nodes=[], file_path=ev.file_path, metadata=ev.metadata, results={})

        tracker = get_tracker()
        file_type = ev.metadata.get("file_type", "document")
        doc_id = ev.metadata.get("doc_id") or ev.metadata.get("id")
        results = await index_nodes(
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
            raise RuntimeError("Failed to index nodes to Qdrant")
        if self.enable_elasticsearch and not results.get("elasticsearch"):
            raise RuntimeError("Failed to index nodes to Elasticsearch")
        if self.enable_neo4j and not results.get("neo4j"):
            raise RuntimeError("Failed to index nodes to Neo4j")

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
    run_semantic_linking: bool = True,
    run_community_detection: bool = False,
    run_topic_extraction: bool = False,
    run_citation_linking: bool = False,
    run_temporal_linking: bool = False,
    run_entity_cooccurrence: bool = False,
    invalidate_cache: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    if "return_nodes" in kwargs:
        return_nodes = bool(kwargs.pop("return_nodes"))
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
