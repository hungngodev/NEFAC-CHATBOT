from __future__ import annotations

from typing import Any, Dict, List, Optional

from llama_index.core import Settings

COMMUNITY_SUMMARY_PROMPT = """You are analyzing a community of related entities from a First Amendment and FOIA knowledge graph.

## Entities in this Community
{entity_descriptions}

## Relationships in this Community
{relationships}

## Instructions
Write a 2-3 paragraph summary that:
1. Identifies the key entities and their roles/significance
2. Explains the main themes and topics that connect them
3. Highlights important relationships and patterns

The summary should help answer questions about this topic area without requiring the reader to examine individual entities.

## Summary
"""


class CommunitySummarizer:
    def __init__(
        self,
        driver,
        llm=None,
        database: str = "neo4j",
        max_entities_per_summary: int = 20,
        max_relationships_per_summary: int = 30,
    ):
        self.driver = driver
        self.llm = llm or Settings.llm
        self.database = database
        self.max_entities = max_entities_per_summary
        self.max_relationships = max_relationships_per_summary

    def _execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def summarize_community(self, community_id: str) -> str:
        entities = self._execute_query(
            """
            MATCH (c:Community {id: $id})<-[:IN_COMMUNITY]-(e:__Entity__)
            RETURN e.name as name, e.entity_description as description,
                   labels(e) as labels
            LIMIT $limit
        """,
            {"id": community_id, "limit": self.max_entities},
        )

        relationships = self._execute_query(
            """
            MATCH (c:Community {id: $id})<-[:IN_COMMUNITY]-(e1:__Entity__)
            MATCH (e1)-[r]->(e2:__Entity__)-[:IN_COMMUNITY]->(c)
            RETURN e1.name as source, e2.name as target,
                   type(r) as relation, r.relationship_description as description
            LIMIT $limit
        """,
            {"id": community_id, "limit": self.max_relationships},
        )

        entity_lines = []
        for e in entities:
            labels = [label for label in (e.get("labels") or []) if not label.startswith("__")]
            label_str = f" ({', '.join(labels)})" if labels else ""
            desc = e.get("description") or "No description available"
            entity_lines.append(f"- **{e['name']}**{label_str}: {desc}")

        entity_text = "\n".join(entity_lines) if entity_lines else "No entities found"

        rel_lines = []
        for r in relationships:
            desc = r.get("description") or ""
            rel_lines.append(f"- {r['source']} --[{r['relation']}]--> {r['target']}" + (f": {desc}" if desc else ""))

        rel_text = "\n".join(rel_lines) if rel_lines else "No relationships found"

        prompt = COMMUNITY_SUMMARY_PROMPT.format(
            entity_descriptions=entity_text,
            relationships=rel_text,
        )

        try:
            response = self.llm.complete(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Summary generation failed: {e}"

    def summarize_all_communities(
        self,
        level: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        if level is not None:
            communities = self._execute_query("MATCH (c:Community) WHERE c.level = $level RETURN c.id as id", {"level": level})
        else:
            communities = self._execute_query("MATCH (c:Community) RETURN c.id as id")

        summaries = {}
        for i, comm in enumerate(communities):
            community_id = comm["id"]

            summary = self.summarize_community(community_id)
            summaries[community_id] = summary

            if not dry_run:
                self._execute_query("MATCH (c:Community {id: $id}) SET c.summary = $summary", {"id": community_id, "summary": summary})

        if not dry_run and summaries:
            try:
                self._execute_query(
                    """
                    CREATE FULLTEXT INDEX community_summaries IF NOT EXISTS
                    FOR (c:Community) ON EACH [c.summary]
                """
                )
            except Exception as e:
                import logging

                logging.getLogger(__name__).debug(f"Failed to create fulltext index: {e}")
        return {
            "communities_summarized": len(summaries),
            "dry_run": dry_run,
            "summaries": summaries if dry_run else None,
        }

    def search_summaries(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            results = self._execute_query(
                """
                CALL db.index.fulltext.queryNodes('community_summaries', $query)
                YIELD node, score
                WHERE score > 0.5
                RETURN node.id as community_id, node.summary as summary,
                       node.level as level, score
                ORDER BY score DESC
                LIMIT $limit
            """,
                {"query": query, "limit": limit},
            )

            return results
        except Exception:
            return []

    def get_summary(self, community_id: str) -> Optional[str]:
        result = self._execute_query("MATCH (c:Community {id: $id}) RETURN c.summary as summary", {"id": community_id})
        if result:
            return result[0].get("summary")
        return None
