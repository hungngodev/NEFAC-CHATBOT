"""
Custom retrievers for the NEFAC knowledge graph.

Provides specialized retrievers that leverage the graph structure:
- EntityAwareRetriever: Extract entities from query, retrieve context for each
- GlobalSearchRetriever: Use community summaries for global/abstract queries
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from llama_index.core import Settings
from llama_index.core.indices.property_graph import (
    CustomPGRetriever,
    VectorContextRetriever,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedEntities(BaseModel):
    """Entities extracted from a user query."""

    entities: List[str] = Field(default_factory=list, description="Named entities mentioned in the query")


class EntityAwareRetriever(CustomPGRetriever):
    """
    Custom retriever that extracts entities from the query and retrieves
    context for each entity.

    This enables more precise retrieval by focusing on the specific entities
    the user is asking about, rather than relying solely on semantic similarity.
    """

    vector_retriever: Optional[VectorContextRetriever] = None

    def init(
        self,
        llm=None,
        embed_model=None,
        similarity_top_k: int = 4,
        path_depth: int = 2,
        include_text: bool = True,
    ):
        """
        Initialize the entity-aware retriever.

        Args:
            llm: Language model for entity extraction
            embed_model: Embedding model for vector search
            similarity_top_k: Number of similar nodes to retrieve per entity
            path_depth: Depth of path traversal from matched nodes
            include_text: Whether to include source text in results
        """
        self.llm = llm or Settings.llm
        self.embed_model = embed_model or Settings.embed_model
        self.similarity_top_k = similarity_top_k
        self.path_depth = path_depth
        self.include_text = include_text

        # Set up vector retriever for fallback
        try:
            self.vector_retriever = VectorContextRetriever(
                self.graph_store,
                embed_model=self.embed_model,
                similarity_top_k=similarity_top_k,
                path_depth=path_depth,
                include_text=include_text,
            )
        except Exception as e:
            logger.warning(f"Could not initialize VectorContextRetriever: {e}")
            self.vector_retriever = None

    def _extract_entities(self, query_str: str) -> List[str]:
        """
        Extract named entities from the query using the LLM.

        Args:
            query_str: The user's query

        Returns:
            List of extracted entity names
        """
        prompt = f"""Extract named entities from this question about First Amendment rights, FOIA, or media law.

Question: {query_str}

Return a JSON object with an "entities" key containing a list of entity names.
Only include actual named entities (people, organizations, laws, cases, etc.).
If no entities are found, return {{"entities": []}}.

JSON:"""

        try:
            response = self.llm.complete(prompt)
            import json

            # Clean response
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            data = json.loads(text)
            entities = data.get("entities", [])

            logger.debug(f"Extracted entities from query: {entities}")
            return entities

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []

    def custom_retrieve(self, query_str: str) -> str:
        """
        Retrieve context by first extracting entities, then retrieving for each.

        Args:
            query_str: The user's query

        Returns:
            Combined context string from all entity matches
        """
        # Extract entities from query
        entities = self._extract_entities(query_str)

        all_nodes = []

        if entities and self.vector_retriever:
            # Retrieve context for each entity
            for entity in entities:
                try:
                    nodes = self.vector_retriever.retrieve(entity)
                    all_nodes.extend(nodes)
                except Exception as e:
                    logger.warning(f"Failed to retrieve for entity '{entity}': {e}")

        # Fallback to full query if no entities or no results
        if not all_nodes and self.vector_retriever:
            try:
                all_nodes = self.vector_retriever.retrieve(query_str)
            except Exception as e:
                logger.warning(f"Fallback retrieval failed: {e}")

        # Deduplicate by node ID
        seen_ids = set()
        unique_nodes = []
        for node in all_nodes:
            node_id = getattr(node, "id_", None) or str(node)
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                unique_nodes.append(node)

        # Combine content
        contents = []
        for node in unique_nodes[: self.similarity_top_k * 2]:  # Limit total results
            if hasattr(node, "get_content"):
                contents.append(node.get_content())
            elif hasattr(node, "text"):
                contents.append(node.text)
            else:
                contents.append(str(node))

        return "\n\n---\n\n".join(contents)


class GlobalSearchRetriever(CustomPGRetriever):
    """
    Retriever that uses community summaries for global/abstract queries.

    Best suited for questions that require broad understanding of the dataset
    rather than specific entity information. Follows Microsoft GraphRAG's
    global search approach.
    """

    def init(
        self,
        driver=None,
        database: str = "neo4j",
        top_k: int = 5,
        min_score: float = 0.5,
    ):
        """
        Initialize the global search retriever.

        Args:
            driver: Neo4j driver (if not using graph_store)
            database: Neo4j database name
            top_k: Number of community summaries to retrieve
            min_score: Minimum relevance score for summaries
        """
        self.top_k = top_k
        self.min_score = min_score
        self.database = database

        # Get driver from graph_store or use provided
        if driver:
            self.driver = driver
        elif hasattr(self, "graph_store"):
            self.driver = getattr(self.graph_store, "driver", None) or getattr(self.graph_store, "_driver", None)
        else:
            self.driver = None

    def _execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Execute a Cypher query."""
        if not self.driver:
            return []

        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def custom_retrieve(self, query_str: str) -> str:
        """
        Retrieve relevant community summaries for the query.

        Args:
            query_str: The user's query

        Returns:
            Combined community summary context
        """
        if not self.driver:
            logger.warning("No Neo4j driver available for global search")
            return ""

        try:
            # Search community summaries using fulltext index
            results = self._execute_query(
                """
                CALL db.index.fulltext.queryNodes('community_summaries', $query)
                YIELD node, score
                WHERE score > $min_score
                RETURN node.id as community_id, node.summary as summary,
                       node.level as level, score
                ORDER BY score DESC
                LIMIT $limit
            """,
                {
                    "query": query_str,
                    "min_score": self.min_score,
                    "limit": self.top_k,
                },
            )

            if not results:
                logger.debug("No community summaries matched the query")
                return ""

            # Format results
            context_parts = ["## Relevant Knowledge Graph Communities\n"]

            for r in results:
                level = r.get("level", "?")
                community_id = r.get("community_id", "unknown")
                score = r.get("score", 0)
                summary = r.get("summary", "")

                context_parts.append(f"### Community {community_id} (Level {level}, Relevance: {score:.2f})\n" f"{summary}\n")

            return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"Global search failed: {e}")
            return ""


class HybridRetriever(CustomPGRetriever):
    """
    Hybrid retriever that combines entity-aware and global search strategies.

    Uses entity extraction for specific questions and falls back to
    community summaries for broader/abstract questions.
    """

    def init(
        self,
        llm=None,
        embed_model=None,
        driver=None,
        similarity_top_k: int = 4,
        path_depth: int = 2,
        global_top_k: int = 3,
    ):
        """Initialize both entity and global retrievers."""
        self.llm = llm or Settings.llm

        # Initialize sub-retrievers
        self.entity_retriever = EntityAwareRetriever(graph_store=self.graph_store)
        self.entity_retriever.init(
            llm=self.llm,
            embed_model=embed_model,
            similarity_top_k=similarity_top_k,
            path_depth=path_depth,
        )

        self.global_retriever = GlobalSearchRetriever(graph_store=self.graph_store)
        self.global_retriever.init(
            driver=driver,
            top_k=global_top_k,
        )

    def _is_global_query(self, query_str: str) -> bool:
        """
        Determine if a query should use global search.

        Global queries typically ask about themes, summaries, or patterns
        rather than specific entities.
        """
        global_keywords = [
            "what are the main",
            "summarize",
            "overview",
            "themes",
            "most significant",
            "overall",
            "in general",
            "broadly",
            "key topics",
            "major issues",
            "common patterns",
        ]

        query_lower = query_str.lower()
        return any(kw in query_lower for kw in global_keywords)

    def custom_retrieve(self, query_str: str) -> str:
        """
        Retrieve using the appropriate strategy based on query type.

        Args:
            query_str: The user's query

        Returns:
            Combined context from both strategies
        """
        parts = []

        # Always try entity-based retrieval
        entity_context = self.entity_retriever.custom_retrieve(query_str)
        if entity_context:
            parts.append("## Entity-Based Context\n" + entity_context)

        # Add global context for broad queries or as supplementary info
        if self._is_global_query(query_str) or not entity_context:
            global_context = self.global_retriever.custom_retrieve(query_str)
            if global_context:
                parts.append(global_context)

        return "\n\n".join(parts) if parts else ""
