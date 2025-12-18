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
    SchemaLLMPathExtractor,
)
from llama_index.core.schema import BaseNode
from llama_index.core.schema import Document as LIDocument
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.llms.openai import OpenAI as LIOpenAI
from openai import RateLimitError

from src.service.ingestion_service.graph.entity_deduplication import (
    EntityDeduplicator,
)
from src.service.ingestion_service.graph.graphrag_extractor import (
    GraphRAGExtractor,
)
from src.service.ingestion_service.graph.linkers import (
    CitationLinker,
    CommunityLinker,
    EntityCooccurrenceLinker,
    SemanticLinker,
    TemporalLinker,
    TopicLinker,
)
from src.service.ingestion_service.llamaindex.metadata_utils import (
    sanitize_metadata,
)
from src.service.ingestion_service.observability import log_debug, log_warning
from src.service.ingestion_service.settings import (
    ALLOWED_NODES,
    ALLOWED_RELATIONSHIPS,
    EMBEDDING_DIMENSIONS,
    ENTITY_ALIASES,
    GRAPH_ENABLE_ENTITY_DEDUPLICATION,
    GRAPH_ENTITY_SIMILARITY_THRESHOLD,
    GRAPH_MAX_TRIPLETS_PER_CHUNK,
    GRAPH_NUM_WORKERS,
    GRAPH_RATE_LIMIT_BACKOFF,
    GRAPH_RATE_LIMIT_RETRIES,
    GRAPH_WORD_DISTANCE_THRESHOLD,
    KG_VALIDATION_SCHEMA,
)

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("llama_index.llms.openai").setLevel(logging.WARNING)


NEFAC_GRAPH_SYSTEM_PROMPT = f"""
You are an expert knowledge graph extractor for the New England First Amendment Coalition.
Your goal is to extract meaningful entities and relationships that represent the content accurately.

Suggested Node Labels (use these if applicable, but feel free to create new ones):
{", ".join(ALLOWED_NODES)}

Suggested Relationships (use these if applicable, but feel free to create new ones):
{", ".join(ALLOWED_RELATIONSHIPS)}

Guidelines:
1. Capture the most important entities and relationships in the text.
2. **Strongly recommend** using the suggested Node Labels and Relationships where they fit. Only create new ones if the suggested options are insufficient.
3. **ALWAYS** use PascalCase for Node Labels (e.g., "Organization") and UPPER_SNAKE_CASE for Relationships (e.g., "WORKS_FOR").
4. Ensure entities are connected where possible.
5. Extract properties that add value (e.g., dates, roles, citations).
6. **ABBREVIATION RESOLUTION**: This is critical.
   - Always look for in-text definitions of abbreviations (e.g., "Body Worn Camera (BWC)" or "BWC, which stands for Body Worn Camera").
   - If you find a definition, ALWAYS use the full name (e.g., "Body Worn Camera") as the entity name, not the abbreviation.
   - You may add the abbreviation as a property if helpful (e.g., `alias="BWC"`), but the `name` must be the full form.
   - If an abbreviation is used without definition, but you know the full name from context (e.g., "NEFAC"), use the full name.
7. Do not create entities with empty names or generic names (e.g., "Unknown", "N/A", "None").
8. **CRITICAL**: Do not output entities with empty names. If you cannot determine a name, do not create the entity.

Examples
Text: "Jane Doe, NEFAC Executive Director, spoke at a public records workshop in Boston on 2025-04-12."
Emit:
Person(name="Jane Doe") WORKS_FOR Organization(name="NEFAC") {{role_title="Executive Director"}}
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
        use_strict_schema: bool = False,
        use_graphrag_descriptions: bool = False,
    ):
        self.neo4j_url = neo4j_url or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or "neo4j"
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.enable_validation = enable_validation
        self.llm = llm or Settings.llm
        self.use_strict_schema = use_strict_schema
        self.use_graphrag_descriptions = use_graphrag_descriptions
        self._setup_graph_store()

    def _setup_graph_store(self):
        self.graph_store = Neo4jPropertyGraphStore(
            username=self.neo4j_user,
            password=self.neo4j_password,
            url=self.neo4j_url,
            database=self.database,
        )
        self._ensure_constraints()

    def _ensure_constraints(self):
        driver = self._get_driver()
        queries = [
            "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:__Entity__) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE INDEX doc_date IF NOT EXISTS FOR (d:__Document__) ON (d.date)",
            "CREATE INDEX case_citation IF NOT EXISTS FOR (c:LegalCase) ON (c.citation)",
            "CREATE INDEX org_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
            "CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name)",
        ]
        with driver.session(database=self.database) as session:
            for q in queries:
                session.run(q)

    def _create_schema_extractor(self):
        extraction_llm = LIOpenAI(
            model=self.llm.model,
            temperature=0.0,
            system_prompt=NEFAC_GRAPH_SYSTEM_PROMPT,
            additional_kwargs=self.llm.additional_kwargs,
        )

        if self.use_strict_schema:
            return SchemaLLMPathExtractor(
                llm=extraction_llm,
                possible_entities=ALLOWED_NODES,
                possible_relations=ALLOWED_RELATIONSHIPS,
                kg_validation_schema=KG_VALIDATION_SCHEMA,
                strict=True,
                num_workers=min(GRAPH_NUM_WORKERS, 4),
                max_triplets_per_chunk=GRAPH_MAX_TRIPLETS_PER_CHUNK,
            )
        else:
            return DynamicLLMPathExtractor(
                llm=extraction_llm,
                allowed_entity_types=ALLOWED_NODES,
                allowed_relation_types=ALLOWED_RELATIONSHIPS,
                num_workers=min(GRAPH_NUM_WORKERS, 4),
                max_triplets_per_chunk=GRAPH_MAX_TRIPLETS_PER_CHUNK,
            )

    def _pre_disambiguate_entities(self, nodes: List[BaseNode]) -> List[BaseNode]:
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
                    pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                    if pattern.search(new_content):
                        found_aliases.append(alias)
                        new_content = pattern.sub(canon, new_content)
            if found_aliases:
                new_node.metadata["original_mentions"] = list(set(found_aliases))
            new_node.set_content(new_content)
            fixed_nodes.append(new_node)
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
        with driver.session(database=self.database) as session:
            session.run(cypher, ids=list(ids))

    def delete_by_doc_id(self, doc_id: str) -> None:
        if not doc_id:
            return
        driver = self._get_driver()
        cypher = """
        MATCH (n {doc_id: $doc_id})
        DETACH DELETE n
        """
        with driver.session(database=self.database) as session:
            session.run(cypher, doc_id=doc_id)

    def _cleanup_empty_nodes(self):
        driver = self._get_driver()
        query = """
        MATCH (n:__Entity__)
        WHERE n.id IS NULL OR toString(n.id) = '' OR n.name IS NULL OR toString(n.name) = ''
        DETACH DELETE n
        """
        with driver.session(database=self.database) as session:
            session.run(query)

    def _link_chunks_to_parent_document(self):
        driver = self._get_driver()
        query = """
        MATCH (c:Chunk)
        WHERE c.doc_id IS NOT NULL
        MERGE (d:__Document__ {id: c.doc_id})
        ON CREATE SET
            d.filename = c.filename,
            d.file_type = c.file_type,
            d.date = c.date,
            d.title = c.title,
            d.source_url = c.source_url,
            d.created_at = datetime()
        ON MATCH SET
            d.filename = coalesce(d.filename, c.filename),
            d.file_type = coalesce(d.file_type, c.file_type),
            d.date = coalesce(d.date, c.date),
            d.title = coalesce(d.title, c.title),
            d.source_url = coalesce(d.source_url, c.source_url)
        MERGE (c)-[:PART_OF]->(d)
        """
        with driver.session(database=self.database) as session:
            session.run(query)

    def _link_entities_to_documents(self):
        driver = self._get_driver()
        query = """
        MATCH (e:__Entity__)-[:MENTIONED_IN|MENTIONS|MENTIONED]->(c:Chunk)-[:PART_OF]->(d:__Document__)
        MERGE (e)-[:APPEARS_IN]->(d)
        """
        with driver.session(database=self.database) as session:
            session.run(query)

    def _link_documents_by_shared_entities(self):
        driver = self._get_driver()
        query = """
        MATCH (d1:__Document__)<-[:APPEARS_IN]-(e:__Entity__)-[:APPEARS_IN]->(d2:__Document__)
        WHERE elementId(d1) < elementId(d2)
        WITH d1, d2, count(e) as shared_count
        WHERE shared_count >= 1
        MERGE (d1)-[r:RELATED_TO]->(d2)
        SET r.weight = shared_count
        """
        with driver.session(database=self.database) as session:
            session.run(query)

    def _link_documents_to_years(self):
        driver = self._get_driver()
        query = r"""
        MATCH (d:__Document__)
        WHERE d.date IS NOT NULL AND d.date =~ '^\d{4}.*'
        WITH d, substring(d.date, 0, 4) as year
        MERGE (y:Year {name: year})
        MERGE (d)-[:PUBLISHED_IN]->(y)
        """
        with driver.session(database=self.database) as session:
            session.run(query)

    def _sync_chunk_metadata(self, documents: List[LIDocument]):
        driver = self._get_driver()

        data = []
        for doc in documents:
            meta = doc.metadata
            item = {
                "id": doc.id_,
                "date": meta.get("date"),
                "title": meta.get("title"),
                "source_url": meta.get("source_url"),
                "file_type": meta.get("file_type"),
                "filename": meta.get("filename"),
            }
            data.append(item)

        query = """
        UNWIND $data AS row
        MATCH (c:Chunk {id: row.id})
        SET c.date = row.date,
            c.title = row.title,
            c.source_url = row.source_url,
            c.file_type = row.file_type,
            c.filename = row.filename
        """

        with driver.session(database=self.database) as session:
            batch_size = 1000
            for i in range(0, len(data), batch_size):
                batch = data[i : i + batch_size]
                session.run(query, data=batch)

    def _normalize_graph_labels(self):
        driver = self._get_driver()
        queries = []

        existing_labels = set()
        existing_rel_types = set()

        try:
            with driver.session(database=self.database) as session:
                result = session.run("CALL db.labels()")
                existing_labels = {record["label"] for record in result}

                result = session.run("CALL db.relationshipTypes()")
                existing_rel_types = {record["relationshipType"] for record in result}
        except Exception as e:
            log_debug("Failed to fetch labels/relationships for normalization", error=e)
            return

        def _clean_key(s: str) -> str:
            return s.lower().replace("_", "").replace(" ", "")

        canonical_labels = {_clean_key(n): n for n in ALLOWED_NODES}

        for label in existing_labels:
            if label in ALLOWED_NODES:
                continue

            clean_label = _clean_key(label)
            if clean_label in canonical_labels:
                correct_label = canonical_labels[clean_label]
                queries.append(
                    f"""
                MATCH (n:`{label}`)
                REMOVE n:`{label}`
                SET n:`{correct_label}`
                """
                )

        canonical_rels = {_clean_key(r): r for r in ALLOWED_RELATIONSHIPS}

        for rel_type in existing_rel_types:
            if rel_type in ALLOWED_RELATIONSHIPS:
                continue

            clean_rel = _clean_key(rel_type)
            if clean_rel in canonical_rels:
                correct_rel = canonical_rels[clean_rel]
                queries.append(
                    f"""
                MATCH ()-[r:`{rel_type}`]->()
                CALL apoc.refactor.setType(r, '{correct_rel}') YIELD input, output
                RETURN count(*)
                """
                )

        try:
            with driver.session(database=self.database) as session:
                for q in queries:
                    session.run(q)
        except Exception as e:
            log_debug("Failed to normalize graph labels", error=e, stage="normalize")

    def _enforce_schema_compliance(self, nodes: List[BaseNode]) -> List[BaseNode]:
        return nodes

    def _cleanup_aggressive(self):
        driver = self._get_driver()
        queries = [
            """
            MATCH (n:__Entity__)
            WHERE n.name IS NULL OR toString(n.name) = '' OR toLower(n.name) IN ['unknown', 'n/a', 'none']
            DETACH DELETE n
            """,
            """
            MATCH (n)
            WHERE size(labels(n)) = 0
            DETACH DELETE n
            """,
        ]
        try:
            with driver.session(database=self.database) as session:
                for q in queries:
                    session.run(q)
        except Exception as e:
            log_debug("Aggressive cleanup failed", error=e, stage="cleanup")

    def ingest_nodes(
        self,
        nodes: List[BaseNode],
        show_progress: bool = True,
        run_deduplication: bool = True,
        run_semantic_linking: bool = True,
        run_community_detection: bool = False,
        run_topic_extraction: bool = False,
        run_citation_linking: bool = False,
        run_temporal_linking: bool = False,
        run_entity_cooccurrence: bool = False,
    ) -> PropertyGraphIndex:
        def _is_rate_limit_error(exc: Exception) -> bool:
            if RateLimitError is not None and isinstance(exc, RateLimitError):
                return True
            msg = str(exc).lower()
            return "rate limit" in msg or "rate_limit_exceeded" in msg

        max_attempts = GRAPH_RATE_LIMIT_RETRIES
        delay = GRAPH_RATE_LIMIT_BACKOFF
        attempt = 0
        while attempt < max_attempts:
            try:

                nodes_to_process = self._pre_disambiguate_entities(nodes)

                documents = self._nodes_to_documents(nodes_to_process)
                ids = [d.id_ for d in documents]
                dupes = {i for i in ids if ids.count(i) > 1}
                if dupes:
                    raise ValueError(f"Duplicate graph node ids in batch: {dupes}")
                incoming_ids = {str(doc.id_) for doc in documents if doc.id_}
                self._delete_existing_node_ids(incoming_ids)

                kg_extractor = self._create_schema_extractor()
                implicit_extractor = ImplicitPathExtractor()

                extractors = [kg_extractor, implicit_extractor]

                if self.use_graphrag_descriptions:
                    graphrag_extractor = GraphRAGExtractor(llm=self.llm)  # type: ignore[arg-type]
                    extractors.append(graphrag_extractor)

                index = PropertyGraphIndex.from_documents(
                    documents,
                    property_graph_store=self.graph_store,
                    kg_extractors=extractors,
                    show_progress=show_progress,
                )

                self._sync_chunk_metadata(documents)
                self._cleanup_aggressive()
                self._label_chunk_nodes()
                self._link_chunks_to_parent_document()
                self._link_entities_to_documents()
                self._link_documents_by_shared_entities()
                self._link_documents_to_years()

                self._normalize_graph_labels()

                if run_semantic_linking:
                    try:
                        semantic_linker = SemanticLinker(self._get_driver())
                        semantic_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Semantic linking failed", error=e, stage="semantic_linking")
                if run_community_detection:
                    try:
                        community_linker = CommunityLinker(self._get_driver())
                        community_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Community detection failed", error=e, stage="community_detection")
                if run_topic_extraction:
                    try:
                        topic_linker = TopicLinker(self._get_driver(), llm=self.llm)
                        topic_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Topic extraction failed", error=e, stage="topic_extraction")
                if run_citation_linking:
                    try:
                        citation_linker = CitationLinker(self._get_driver())
                        citation_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Citation linking failed", error=e, stage="citation_linking")
                if run_temporal_linking:
                    try:
                        temporal_linker = TemporalLinker(self._get_driver())
                        temporal_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Temporal linking failed", error=e, stage="temporal_linking")
                if run_entity_cooccurrence:
                    try:
                        cooccurrence_linker = EntityCooccurrenceLinker(self._get_driver())
                        cooccurrence_linker.apply_links(ids)
                    except Exception as e:
                        log_warning("Entity cooccurrence linking failed", error=e, stage="cooccurrence_linking")
                if run_deduplication and GRAPH_ENABLE_ENTITY_DEDUPLICATION:
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
                    time.sleep(sleep_for)
                    continue
                raise
        raise RuntimeError("Max retries exhausted without success")

    def deduplicate_entities(
        self,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
        dry_run: bool = False,
    ) -> dict:
        deduplicator = EntityDeduplicator(
            graph_store=self.graph_store,
            similarity_threshold=similarity_threshold,
            word_edit_distance=word_edit_distance,
            enable_apoc=enable_apoc,
            llm=Settings.llm,
        )
        deduplicator.create_vector_index(embedding_dimension=EMBEDDING_DIMENSIONS, name="entity_vec_idx")

        duplicate_groups = deduplicator.find_duplicate_entities()

        validated_groups, false_positives = deduplicator.validate_duplicates(duplicate_groups)

        initial_stats = deduplicator.get_duplicate_stats(duplicate_groups=duplicate_groups, validated_groups=validated_groups, false_positives=false_positives)

        merge_stats = deduplicator.merge_duplicate_entities(
            duplicate_groups=validated_groups,
            dry_run=dry_run,
        )
        final_stats = deduplicator.get_duplicate_stats(use_llm=False)
        return {
            **merge_stats,
            "initial_stats": initial_stats,
            "final_stats": final_stats,
            "validated_groups": len(validated_groups),
            "false_positives_filtered": len(false_positives),
        }

    def _get_driver(self):
        driver = getattr(self.graph_store, "driver", None) or getattr(self.graph_store, "_driver", None)
        if driver is None:
            raise RuntimeError("Neo4j driver not available from property graph store")
        return driver

    def clear_graph(self):
        driver = self._get_driver()
        with driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def get_stats(self) -> dict:
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

    def _label_chunk_nodes(self):
        driver = self._get_driver()

        query_text = """
        MATCH (n:Chunk)
        WHERE n.name IS NULL AND n.text IS NOT NULL
        SET n.name = 'Chunk: ' + substring(n.text, 0, 30) + '...'
        """

        query_standard = """
        MATCH (n:Chunk)
        WHERE n.name IS NULL
        SET n.name = 'Chunk ' + coalesce(toString(n.chunk_index), '?') + ' of ' + coalesce(n.filename, 'Unknown')
        """

        query_cleanup = """
        MATCH (n:Chunk)
        WHERE n.text IS NULL AND n.filename IS NULL AND n.chunk_index IS NULL
        DETACH DELETE n
        """

        with driver.session(database=self.database) as session:
            session.run(query_text)
            session.run(query_standard)
            session.run(query_cleanup)
