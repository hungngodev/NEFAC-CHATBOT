from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import time
from typing import List, Optional, Set

from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import (
    DynamicLLMPathExtractor,
    ImplicitPathExtractor,
)
from llama_index.core.schema import BaseNode
from llama_index.core.schema import Document as LIDocument
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from openai import RateLimitError

from src.config.models import EMBEDDING_DIMENSIONS
from src.service.ingestion_service.llamaindex.entity_deduplication import (
    EntityDeduplicator,
)
from src.service.ingestion_service.llamaindex.metadata_utils import (
    sanitize_metadata,
)
from src.service.ingestion_service.settings import (
    ALLOWED_NODES,
    ALLOWED_RELATIONSHIPS,
    ENTITY_ALIASES,
    GRAPH_ENABLE_ENTITY_DEDUPLICATION,
    GRAPH_ENTITY_SIMILARITY_THRESHOLD,
    GRAPH_MAX_TRIPLETS_PER_CHUNK,
    GRAPH_NUM_WORKERS,
    GRAPH_WORD_DISTANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("llama_index.llms.openai").setLevel(logging.WARNING)


NEFAC_GRAPH_SYSTEM_PROMPT = """
You are an expert knowledge graph extractor for the New England First Amendment Coalition.
Your goal is to extract meaningful entities and relationships that represent the content accurately.

Suggested Node Labels (use these if applicable, but feel free to create new ones):
Person, Organization, Program, Event, Document, MediaAsset, LegalCase,
LawOrPolicy, Location, WebPage, Dataset, FundingSource, Board, Committee, SocialProfile.

Suggested Relationships (use these if applicable, but feel free to create new ones):
WORKS_FOR, SERVES_ON, PARTNERS_WITH, HOSTED_BY, TAKES_PLACE_IN, LOCATED_IN,
AUTHORED_BY, WRITES, PUBLISHES, FILES, DECIDED_BY, CITES, REFERENCES,
CHALLENGES, FUNDS, ANNOUNCES, HAS_PAGE, HAS_SECTION, LINKS_TO, HAS_PROFILE.

Guidelines:
1. Capture the most important entities and relationships in the text.
2. Use the suggested labels where they fit, but do not force them if a better label exists.
3. Ensure entities are connected where possible.
4. Extract properties that add value (e.g., dates, roles, citations).

Examples
Text: "Jane Doe, NEFAC Executive Director, spoke at a public records workshop in Boston on 2025-04-12."
Emit:
Person(name="Jane Doe") WORKS_FOR Organization(name="NEFAC") {role_title="Executive Director"}
Event(type="Workshop", name="Public Records Workshop", start_date="2025-04-12") HOSTED_BY Organization("NEFAC")
Event(...) TAKES_PLACE_IN Location(name="Boston, MA")

Text: "NEFAC filed an amicus brief citing Doe v. City, 555 F.3d 123."
Emit:
Document(type="AmicusBrief", title="...", date_published="...") FILES Organization("NEFAC")
Document(...) CITES LegalCase(citation="555 F.3d 123", name="Doe v. City")
"""


class LegalPropertyGraphIngestor:
    def __init__(
        self,
        neo4j_url: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        database: str = "neo4j",
        enable_validation: bool = True,
        llm=None,
    ):
        self.neo4j_url = neo4j_url or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.enable_validation = enable_validation
        self.llm = llm or Settings.llm
        self._setup_graph_store()

    def _setup_graph_store(self):
        try:
            self.graph_store = Neo4jPropertyGraphStore(
                username=self.neo4j_user,
                password=self.neo4j_password,
                url=self.neo4j_url,
                database=self.database,
            )
            logger.info(f"Connected to Neo4j at {self.neo4j_url}")
            self._ensure_constraints()
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _ensure_constraints(self):
        """Create constraints and indexes to prevent duplicates and speed up queries."""
        driver = self._get_driver()
        queries = [
            "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:__Entity__) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX doc_date IF NOT EXISTS FOR (d:Document) ON (d.date_published)",
            "CREATE INDEX case_citation IF NOT EXISTS FOR (c:LegalCase) ON (c.citation)",
            "CREATE INDEX org_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
            "CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name)",
        ]
        try:
            with driver.session(database=self.database) as session:
                for q in queries:
                    session.run(q)
            logger.info("Ensured Neo4j constraints and indexes exist")
        except Exception as e:
            logger.warning(f"Could not create constraints: {e}")

    def _create_schema_extractor(self):
        logger.info("Creating DynamicLLMPathExtractor with legal domain schema")

        from llama_index.llms.openai import OpenAI as LIOpenAI

        extraction_llm = LIOpenAI(
            model=self.llm.model,
            temperature=0.0,
            system_prompt=NEFAC_GRAPH_SYSTEM_PROMPT,
            additional_kwargs=self.llm.additional_kwargs,
        )
        logger.info("Created specialized extraction LLM with system prompt and flex tier")

        extractor_kwargs = {
            "llm": extraction_llm,
            "allowed_entity_types": ALLOWED_NODES,
            "allowed_relation_types": ALLOWED_RELATIONSHIPS,
            "num_workers": min(GRAPH_NUM_WORKERS, 4),
            "max_triplets_per_chunk": GRAPH_MAX_TRIPLETS_PER_CHUNK,
        }
        return DynamicLLMPathExtractor(**extractor_kwargs)

    def _pre_disambiguate_entities(self, nodes: List[BaseNode]) -> List[BaseNode]:
        logger.info("Disambiguating entities for %d nodes...", len(nodes))
        fixed_nodes = []
        for node in nodes:
            new_node = node.model_copy()
            content = new_node.get_content()
            new_content = content
            found_aliases = []
            for canon, aliases in ENTITY_ALIASES.items():
                for alias in aliases:
                    if alias == canon:
                        continue
                    # Use word boundaries to avoid partial matches
                    pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                    if pattern.search(new_content):
                        found_aliases.append(alias)
                        new_content = pattern.sub(canon, new_content)
            if found_aliases:
                new_node.metadata["original_mentions"] = list(set(found_aliases))
            new_node.set_content(new_content)
            fixed_nodes.append(new_node)
        logger.info("Entity disambiguation complete for %d nodes", len(fixed_nodes))
        return fixed_nodes

    def _nodes_to_documents(self, nodes: List[BaseNode]) -> List[LIDocument]:
        documents = []
        for idx, node in enumerate(nodes):
            metadata = sanitize_metadata(dict(node.metadata or {}), keep_summary=False)
            doc_id = metadata.get("doc_id") or metadata.get("document_id") or metadata.get("ref_doc_id") or metadata.get("id")
            if doc_id:
                metadata["doc_id"] = doc_id
            chunk_index = idx

            h = hashlib.sha1(f"{doc_id}:{idx}".encode()).hexdigest()[:12]
            chunk_id = f"{doc_id}__{h}"

            metadata["chunk_index"] = chunk_index
            metadata["chunk_id"] = chunk_id

            keys_to_remove = ["contextual_summary", "section_summary", "id", "questions_this_excerpt_can_answer", "excerpt_keywords", "text", "embedding", "_node_content"]
            for key in keys_to_remove:
                metadata.pop(key, None)

            documents.append(LIDocument(text=node.get_content(), metadata=metadata, id_=chunk_id))
        return documents

    def _delete_existing_node_ids(self, ids: Set[str]) -> None:
        if not ids:
            return
        driver = self._get_driver()
        cypher = """
        UNWIND $ids AS rid
        MATCH (n {chunk_id: rid})
        DETACH DELETE n
        """
        try:
            with driver.session(database=self.database) as session:
                session.run(cypher, ids=list(ids))
        except Exception as exc:
            logger.warning("Could not pre-delete duplicate nodes by chunk_id: %s", exc)

    def delete_by_doc_id(self, doc_id: str) -> None:
        if not doc_id:
            return
        driver = self._get_driver()
        cypher = """
        MATCH (n {doc_id: $doc_id})
        DETACH DELETE n
        """
        try:
            with driver.session(database=self.database) as session:
                session.run(cypher, doc_id=doc_id)
            logger.info("Deleted existing graph nodes for doc_id=%s", doc_id)
        except Exception as exc:
            logger.warning("Failed to delete graph nodes for doc_id=%s: %s", doc_id, exc)

    def ingest_nodes(
        self,
        nodes: List[BaseNode],
        show_progress: bool = True,
        run_deduplication: bool = True,
    ) -> PropertyGraphIndex:
        def _is_rate_limit_error(exc: Exception) -> bool:
            if RateLimitError and isinstance(exc, RateLimitError):
                return True
            msg = str(exc).lower()
            return "rate limit" in msg or "rate_limit_exceeded" in msg

        max_attempts = int(os.getenv("GRAPH_RATE_LIMIT_RETRIES", "4"))
        delay = float(os.getenv("GRAPH_RATE_LIMIT_BACKOFF", "5.0"))
        attempt = 0
        while attempt < max_attempts:
            try:
                logger.info(
                    "Ingesting %d nodes into PropertyGraphIndex (attempt %d/%d)",
                    len(nodes),
                    attempt + 1,
                    max_attempts,
                )
                nodes_to_process = self._pre_disambiguate_entities(nodes)
                documents = self._nodes_to_documents(nodes_to_process)
                ids = [d.id_ for d in documents]
                dupes = {i for i in ids if ids.count(i) > 1}
                if dupes:
                    logger.error("Duplicate graph node ids in batch: %s", dupes)
                    raise ValueError(f"Duplicate graph node ids in batch: {dupes}")
                incoming_ids = {str(doc.id_) for doc in documents if doc.id_}
                self._delete_existing_node_ids(incoming_ids)

                kg_extractor = self._create_schema_extractor()
                implicit_extractor = ImplicitPathExtractor()

                index = PropertyGraphIndex.from_documents(
                    documents,
                    property_graph_store=self.graph_store,
                    kg_extractors=[kg_extractor, implicit_extractor],
                    show_progress=show_progress,
                )
                logger.info("Successfully ingested %d nodes into property graph", len(nodes))
                if run_deduplication and GRAPH_ENABLE_ENTITY_DEDUPLICATION:
                    logger.info("Starting entity deduplication...")
                    self.deduplicate_entities(
                        similarity_threshold=GRAPH_ENTITY_SIMILARITY_THRESHOLD,
                        word_edit_distance=int(GRAPH_WORD_DISTANCE_THRESHOLD),
                    )
                return index
            except Exception as e:
                attempt += 1
                if _is_rate_limit_error(e) and attempt < max_attempts:
                    sleep_for = delay * (1.5**attempt) + random.uniform(0, 1.0)
                    sleep_for = min(sleep_for, 30.0)
                    logger.debug(
                        "Rate limited during graph ingestion, backing off %.1fs (attempt %d/%d)",
                        sleep_for,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(sleep_for)
                    continue
                logger.error("Failed to ingest nodes into property graph: %s", e)
                raise

    def deduplicate_entities(
        self,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
        dry_run: bool = False,
    ) -> dict:
        try:
            logger.info(
                "Running entity deduplication (similarity=%.2f, word_distance=%d, dry_run=%s)",
                similarity_threshold,
                word_edit_distance,
                dry_run,
            )
            deduplicator = EntityDeduplicator(
                graph_store=self.graph_store,
                similarity_threshold=similarity_threshold,
                word_edit_distance=word_edit_distance,
                enable_apoc=enable_apoc,
            )
            deduplicator.create_vector_index(embedding_dimension=EMBEDDING_DIMENSIONS, name="entity_vec_idx")
            initial_stats = deduplicator.get_duplicate_stats()
            logger.debug("Duplicate analysis: %s", initial_stats)
            duplicate_groups = deduplicator.find_duplicate_entities()
            validated_groups, false_positives = deduplicator.validate_duplicates(duplicate_groups)
            logger.info(
                "Validated duplicate groups=%d (filtered false positives=%d)",
                len(validated_groups),
                len(false_positives),
            )
            merge_stats = deduplicator.merge_duplicate_entities(
                duplicate_groups=validated_groups,
                dry_run=dry_run,
            )
            final_stats = deduplicator.get_duplicate_stats()
            result = {
                **merge_stats,
                "initial_stats": initial_stats,
                "final_stats": final_stats,
                "validated_groups": len(validated_groups),
                "false_positives_filtered": len(false_positives),
            }
            logger.info(
                "Entity deduplication complete: merged_groups=%s total_entities_merged=%s",
                result.get("merged_groups"),
                result.get("total_entities_merged"),
            )
            return result
        except Exception as e:
            logger.error(f"Error during entity deduplication: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_driver(self):
        driver = getattr(self.graph_store, "driver", None) or getattr(self.graph_store, "_driver", None)
        if driver is None:
            raise RuntimeError("Neo4j driver not available from property graph store")
        return driver

    def clear_graph(self):
        try:
            driver = self._get_driver()
            logger.info("Clearing Neo4j graph")
            with driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Neo4j graph cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    def get_stats(self) -> dict:
        try:
            driver = self._get_driver()
            with driver.session(database=self.database) as session:
                node_count_record = session.run("MATCH (n) RETURN count(n) AS count").single()
                node_count = node_count_record["count"] if node_count_record else 0
                relationship_count_record = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()
                relationship_count = relationship_count_record["count"] if relationship_count_record else 0
                label_counts = []
                for record in session.run(
                    """
                    MATCH (n)
                    WITH labels(n) AS labels
                    UNWIND labels AS label
                    RETURN label, count(*) AS count
                    ORDER BY count DESC
                    LIMIT 10
                    """
                ):
                    label_counts.append({"label": record["label"], "count": record["count"]})
                relationship_type_counts = []
                for record in session.run(
                    """
                    MATCH ()-[r]->()
                    RETURN type(r) AS type, count(*) AS count
                    ORDER BY count DESC
                    LIMIT 10
                    """
                ):
                    relationship_type_counts.append({"type": record["type"], "count": record["count"]})
            return {
                "nodes": node_count,
                "relationships": relationship_count,
                "top_labels": label_counts,
                "top_relationship_types": relationship_type_counts,
            }
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"error": str(e)}
