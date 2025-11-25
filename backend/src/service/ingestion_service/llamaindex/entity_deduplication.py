"""Enhanced entity deduplication for Neo4j Property Graph.

Based on Neo4j + LlamaIndex tutorial:
https://neo4j.com/blog/developer/property-graph-index-llamaindex/

Combines vector similarity with word edit distance for robust entity matching.
Uses APOC functions for advanced text processing.

Usage as module:
    from entity_deduplication import EntityDeduplicator
    deduplicator = EntityDeduplicator(graph_store)
    stats = deduplicator.get_duplicate_stats()
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from src.service.ingestion_service.settings import (
    GRAPH_ENTITY_SIMILARITY_THRESHOLD,
    GRAPH_WORD_DISTANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


class EntityDeduplicator:
    """Entity deduplication using vector similarity and word distance.

    This class implements the advanced deduplication pattern from the
    Neo4j tutorial, combining:
    1. Vector embedding similarity (semantic matching)
    2. Word edit distance (string similarity)
    3. Label-based filtering (only merge same entity types)
    4. Substring matching (partial name matches)

    The algorithm:
    1. Create vector index on entity embeddings
    2. For each entity, find similar entities using vector search
    3. Filter by similarity threshold and word distance
    4. Group entities that should be merged
    5. Merge duplicate nodes, preserving all relationships
    """

    def __init__(
        self,
        graph_store,
        similarity_threshold: float = 0.9,
        word_edit_distance: int = 5,
        enable_apoc: bool = True,
    ):
        """Initialize entity deduplicator.

        Args:
            graph_store: Neo4jPropertyGraphStore instance
            similarity_threshold: Minimum cosine similarity for duplicates (0-1)
            word_edit_distance: Maximum Levenshtein distance for duplicates
            enable_apoc: Use APOC functions if available
        """
        self.graph_store = graph_store
        self.similarity_threshold = similarity_threshold
        self.word_edit_distance = word_edit_distance
        self.enable_apoc = enable_apoc

        logger.info(f"EntityDeduplicator initialized: " f"similarity_threshold={similarity_threshold}, " f"word_edit_distance={word_edit_distance}")

    def create_vector_index(self, embedding_dimension: int = 1536):
        """Create vector index on entity embeddings.

        Args:
            embedding_dimension: Dimension of embeddings (1536 for OpenAI)
        """
        try:
            query = """
            CREATE VECTOR INDEX entity IF NOT EXISTS
            FOR (m:`__Entity__`)
            ON m.embedding
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }}
            """

            self.graph_store.structured_query(query, param_map={"dimensions": embedding_dimension})

            logger.info(f"Created vector index on __Entity__ with {embedding_dimension} dimensions")

        except Exception as e:
            logger.warning(f"Could not create vector index: {e}")
            logger.info("Continuing without vector index (may impact performance)")

    def find_duplicate_entities(self) -> List[List[str]]:
        """Find groups of duplicate entities.

        Returns:
            List of entity name groups that should be merged.
            Example: [['Microsoft', 'Microsoft Corp'], ['Google', 'Google LLC']]
        """
        try:
            if self.enable_apoc:
                return self._find_duplicates_with_apoc()
            else:
                return self._find_duplicates_without_apoc()
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            return []

    def _find_duplicates_with_apoc(self) -> List[List[str]]:
        """Find duplicates using APOC functions (recommended).

        This is the exact pattern from the Neo4j tutorial.
        """
        query = """
        MATCH (e:__Entity__)
        CALL {
            WITH e
            CALL db.index.vector.queryNodes('entity', 10, e.embedding)
            YIELD node, score
            WITH node, score
            WHERE score > toFloat($cutoff)
                AND (toLower(node.name) CONTAINS toLower(e.name) 
                     OR toLower(e.name) CONTAINS toLower(node.name)
                     OR apoc.text.distance(toLower(node.name), toLower(e.name)) < $distance)
                AND labels(e) = labels(node)
            WITH node, score
            ORDER BY node.name
            RETURN collect(node) AS nodes
        }
        WITH distinct nodes
        WHERE size(nodes) > 1
        WITH collect([n in nodes | n.name]) AS results
        UNWIND range(0, size(results)-1, 1) as index
        WITH results, index, results[index] as result
        WITH apoc.coll.sort(reduce(acc = result, index2 IN range(0, size(results)-1, 1) |
                CASE WHEN index <> index2 AND
                    size(apoc.coll.intersection(acc, results[index2])) > 0
                    THEN apoc.coll.union(acc, results[index2])
                    ELSE acc
                END
        )) as combinedResult
        WITH distinct(combinedResult) as combinedResult
        // Extra filtering to remove subsets
        WITH collect(combinedResult) as allCombinedResults
        UNWIND range(0, size(allCombinedResults)-1, 1) as combinedResultIndex
        WITH allCombinedResults[combinedResultIndex] as combinedResult,
             combinedResultIndex, allCombinedResults
        WHERE NOT any(x IN range(0,size(allCombinedResults)-1,1) 
            WHERE x <> combinedResultIndex
            AND apoc.coll.containsAll(allCombinedResults[x], combinedResult)
        )
        RETURN combinedResult
        """

        try:
            data = self.graph_store.structured_query(query, param_map={"cutoff": self.similarity_threshold, "distance": self.word_edit_distance})

            duplicate_groups = [row["combinedResult"] for row in data]

            logger.info(f"Found {len(duplicate_groups)} duplicate entity groups using APOC")
            for group in duplicate_groups:
                logger.debug(f"Duplicate group: {group}")

            return duplicate_groups

        except Exception as e:
            logger.error(f"Error in APOC-based deduplication: {e}")
            logger.info("Falling back to non-APOC method")
            return self._find_duplicates_without_apoc()

    def _find_duplicates_without_apoc(self) -> List[List[str]]:
        """Find duplicates without APOC (fallback method).

        Uses simpler Cypher without APOC text functions.
        """
        query = """
        MATCH (e:__Entity__)
        CALL {
            WITH e
            CALL db.index.vector.queryNodes('entity', 10, e.embedding)
            YIELD node, score
            WITH node, score
            WHERE score > toFloat($cutoff)
                AND (toLower(node.name) CONTAINS toLower(e.name) 
                     OR toLower(e.name) CONTAINS toLower(node.name))
                AND labels(e) = labels(node)
            WITH node, score
            ORDER BY node.name
            RETURN collect(node.name) AS names
        }
        WITH distinct names
        WHERE size(names) > 1
        RETURN names as combinedResult
        """

        try:
            data = self.graph_store.structured_query(query, param_map={"cutoff": self.similarity_threshold})

            duplicate_groups = [row["combinedResult"] for row in data]

            # Manual post-processing to remove subsets
            filtered_groups = self._remove_subset_groups(duplicate_groups)

            logger.info(f"Found {len(filtered_groups)} duplicate entity groups (no APOC)")
            return filtered_groups

        except Exception as e:
            logger.error(f"Error in non-APOC deduplication: {e}")
            return []

    def _remove_subset_groups(self, groups: List[List[str]]) -> List[List[str]]:
        """Remove groups that are subsets of other groups.

        Args:
            groups: List of entity name lists

        Returns:
            Filtered list without subset groups
        """
        filtered = []
        for i, group in enumerate(groups):
            is_subset = False
            for j, other_group in enumerate(groups):
                if i != j and set(group).issubset(set(other_group)):
                    is_subset = True
                    break
            if not is_subset:
                filtered.append(group)
        return filtered

    def merge_duplicate_entities(
        self,
        duplicate_groups: Optional[List[List[str]]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Merge duplicate entities into single canonical entities.

        Args:
            duplicate_groups: Groups to merge (if None, will find them)
            dry_run: If True, only report what would be merged

        Returns:
            Dictionary with merge statistics
        """
        if duplicate_groups is None:
            duplicate_groups = self.find_duplicate_entities()

        if not duplicate_groups:
            logger.info("No duplicate entities found to merge")
            return {"merged_groups": 0, "total_entities_merged": 0}

        merged_count = 0
        total_entities = 0

        for group in duplicate_groups:
            if len(group) < 2:
                continue

            # Use first entity as canonical (alphabetically first)
            canonical_name = sorted(group)[0]
            duplicates = [name for name in group if name != canonical_name]

            logger.info(f"Merging {duplicates} into '{canonical_name}'")

            if not dry_run:
                self._merge_entity_group(canonical_name, duplicates)

            merged_count += 1
            total_entities += len(duplicates)

        stats = {
            "merged_groups": merged_count,
            "total_entities_merged": total_entities,
            "dry_run": dry_run,
        }

        logger.info(f"Entity deduplication complete: {stats}")
        return stats

    def _merge_entity_group(self, canonical_name: str, duplicates: List[str]):
        """Merge a group of duplicate entities into canonical entity.

        Args:
            canonical_name: The name to keep
            duplicates: Names to merge into canonical
        """
        # Cypher query to merge entities
        # This preserves all relationships from duplicate nodes
        query = """
        MATCH (canonical:__Entity__ {name: $canonical_name})
        MATCH (duplicate:__Entity__)
        WHERE duplicate.name IN $duplicates
            AND labels(canonical) = labels(duplicate)

        // Copy all relationships from duplicate to canonical
        WITH canonical, duplicate
        CALL {
            WITH canonical, duplicate
            MATCH (duplicate)-[r]->(other)
            WHERE NOT (canonical)-[:TYPE(r)]->(other)
            CREATE (canonical)-[new_r:TYPE(r)]->(other)
            SET new_r = properties(r)
            RETURN count(*) as outgoing_rels
        }

        CALL {
            WITH canonical, duplicate
            MATCH (other)-[r]->(duplicate)
            WHERE NOT (other)-[:TYPE(r)]->(canonical)
            CREATE (other)-[new_r:TYPE(r)]->(canonical)
            SET new_r = properties(r)
            RETURN count(*) as incoming_rels
        }

        // Merge properties (keep canonical's if conflict)
        WITH canonical, duplicate, outgoing_rels, incoming_rels
        SET canonical += duplicate {.*, name: canonical.name}

        // Delete duplicate
        DETACH DELETE duplicate

        RETURN canonical.name as merged_into,
               outgoing_rels + incoming_rels as relationships_transferred
        """

        try:
            result = self.graph_store.structured_query(query, param_map={"canonical_name": canonical_name, "duplicates": duplicates})

            if result:
                rel_count = sum(row.get("relationships_transferred", 0) for row in result)
                logger.debug(f"Merged {len(duplicates)} entities into '{canonical_name}', " f"transferred {rel_count} relationships")

        except Exception as e:
            logger.error(f"Error merging entity group: {e}")

    def validate_duplicates(
        self,
        duplicate_groups: Optional[List[List[str]]] = None,
    ) -> Tuple[List[List[str]], List[List[str]]]:
        """Validate duplicate groups and separate true/false positives.

        Args:
            duplicate_groups: Groups to validate (if None, will find them)

        Returns:
            Tuple of (validated_groups, false_positives)
        """
        if duplicate_groups is None:
            duplicate_groups = self.find_duplicate_entities()

        # Known false positive patterns for legal domain
        false_positive_patterns = [
            # Different years/dates
            (lambda names: any("202" in str(n) for n in names), "Contains different years"),
            # Draft vs actual
            (lambda names: any("draft" in str(n).lower() for n in names) and any("draft" not in str(n).lower() for n in names), "Mix of draft and non-draft"),
            # Amended versions
            (lambda names: len(set(str(n).replace("Amended", "").strip() for n in names)) > 1, "Different base documents with amendments"),
        ]

        validated = []
        false_positives = []

        for group in duplicate_groups:
            is_false_positive = False
            reason = None

            for pattern_fn, pattern_reason in false_positive_patterns:
                try:
                    if pattern_fn(group):
                        is_false_positive = True
                        reason = pattern_reason
                        break
                except Exception:
                    pass

            if is_false_positive:
                logger.debug(f"False positive detected: {group} - {reason}")
                false_positives.append(group)
            else:
                validated.append(group)

        logger.info(f"Validation complete: {len(validated)} valid groups, " f"{len(false_positives)} false positives")

        return validated, false_positives

    def get_duplicate_stats(self) -> Dict[str, Any]:
        """Get statistics about entity duplicates.

        Returns:
            Dictionary with duplicate statistics
        """
        try:
            # Count total entities
            count_query = "MATCH (e:__Entity__) RETURN count(e) as total"
            result = self.graph_store.structured_query(count_query)
            total_entities = result[0]["total"] if result else 0

            # Find duplicates
            duplicate_groups = self.find_duplicate_entities()
            validated, false_positives = self.validate_duplicates(duplicate_groups)

            total_duplicates = sum(len(group) - 1 for group in validated)

            stats = {
                "total_entities": total_entities,
                "duplicate_groups_found": len(duplicate_groups),
                "validated_groups": len(validated),
                "false_positive_groups": len(false_positives),
                "total_duplicate_entities": total_duplicates,
                "deduplication_potential": f"{(total_duplicates / max(total_entities, 1) * 100):.1f}%",
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting duplicate stats: {e}")
            return {"error": str(e)}
