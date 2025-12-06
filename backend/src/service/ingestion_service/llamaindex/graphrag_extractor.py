"""
GraphRAG V2-style entity and relationship extractor.

This module implements Microsoft GraphRAG-inspired extraction that enriches
entities and relationships with LLM-generated descriptions for richer context.
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional, Sequence

from llama_index.core.graph_stores.types import (
    KG_NODES_KEY,
    KG_RELATIONS_KEY,
    EntityNode,
    Relation,
)
from llama_index.core.schema import BaseNode, TransformComponent
from llama_index.llms.openai import OpenAI

from src.service.ingestion_service.settings import ALLOWED_NODES, ALLOWED_RELATIONSHIPS

logger = logging.getLogger(__name__)


GRAPHRAG_EXTRACTION_PROMPT = """You are a knowledge graph extraction expert specializing in First Amendment, FOIA, and media law content.

Extract entities and relationships from the text below. For each entity and relationship, provide a detailed description.

## Entity Types (use these)
{entity_types}

## Relationship Types (use these)
{relation_types}

## Instructions
1. Identify all significant entities in the text
2. For each entity, provide:
   - name: The entity's name (PascalCase, no abbreviations)
   - type: One of the entity types above
   - description: A 2-3 sentence description explaining who/what this entity is and its significance

3. For each relationship between entities, provide:
   - source: The source entity name
   - target: The target entity name
   - relation: One of the relationship types above (UPPER_SNAKE_CASE)
   - description: A 1-2 sentence explanation of how these entities are related

## Output Format
Return valid JSON only:
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "..."}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "relation": "...", "description": "..."}}
  ]
}}

## Text to Analyze
{text}
"""


class GraphRAGExtractor(TransformComponent):
    """
    Microsoft GraphRAG-style extractor that enriches entities and relationships
    with LLM-generated descriptions.

    This extractor produces:
    - EntityNodes with `entity_description` property
    - Relations with `relationship_description` property

    These descriptions enable:
    - Richer semantic search over the knowledge graph
    - Better community summarization
    - More contextual retrieval
    """

    def __init__(
        self,
        llm: Optional[OpenAI] = None,
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        max_retries: int = 3,
    ):
        """
        Initialize the GraphRAG extractor.

        Args:
            llm: Language model to use for extraction (defaults to Settings.llm)
            entity_types: Allowed entity types (defaults to ALLOWED_NODES)
            relation_types: Allowed relationship types (defaults to ALLOWED_RELATIONSHIPS)
            max_retries: Number of retries for failed extractions
        """
        super().__init__()

        if llm is None:
            from llama_index.core import Settings

            self.llm = Settings.llm
        else:
            self.llm = llm

        self.entity_types = entity_types or ALLOWED_NODES
        self.relation_types = relation_types or ALLOWED_RELATIONSHIPS
        self.max_retries = max_retries

    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> List[BaseNode]:
        """
        Process nodes to extract entities and relationships with descriptions.

        Args:
            nodes: List of text nodes to process

        Returns:
            List of nodes with KG_NODES_KEY and KG_RELATIONS_KEY metadata
        """
        for node in nodes:
            try:
                entities, relationships = self._extract_with_descriptions(node)

                # Add entities with descriptions to node metadata
                kg_nodes = node.metadata.get(KG_NODES_KEY, [])
                for entity in entities:
                    entity_node = EntityNode(
                        name=entity["name"],
                        label=entity["type"],
                        properties={
                            "entity_description": entity.get("description", ""),
                        },
                    )
                    kg_nodes.append(entity_node)
                node.metadata[KG_NODES_KEY] = kg_nodes

                # Add relationships with descriptions to node metadata
                kg_relations = node.metadata.get(KG_RELATIONS_KEY, [])
                for rel in relationships:
                    relation = Relation(
                        label=rel["relation"],
                        source_id=rel["source"],
                        target_id=rel["target"],
                        properties={
                            "relationship_description": rel.get("description", ""),
                        },
                    )
                    kg_relations.append(relation)
                node.metadata[KG_RELATIONS_KEY] = kg_relations

            except Exception as e:
                logger.warning(f"Failed to extract from node: {e}")
                continue

        return list(nodes)

    def _extract_with_descriptions(self, node: BaseNode) -> tuple[List[dict], List[dict]]:
        """
        Extract entities and relationships with descriptions from a single node.

        Args:
            node: The node to extract from

        Returns:
            Tuple of (entities, relationships) lists
        """
        text = node.get_content()
        if not text or len(text.strip()) < 50:
            return [], []

        prompt = GRAPHRAG_EXTRACTION_PROMPT.format(
            entity_types=", ".join(self.entity_types),
            relation_types=", ".join(self.relation_types),
            text=text[:4000],  # Limit text length
        )

        for attempt in range(self.max_retries):
            try:
                response = self.llm.complete(prompt)
                response_text = response.text.strip()

                # Handle code blocks
                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    # Remove first and last lines (```json and ```)
                    response_text = "\n".join(lines[1:-1])

                data = json.loads(response_text)

                entities = data.get("entities", [])
                relationships = data.get("relationships", [])

                # Validate and filter
                valid_entities = []
                for e in entities:
                    if e.get("name") and e.get("type"):
                        # Normalize entity type
                        if e["type"] not in self.entity_types:
                            # Try to match case-insensitively
                            for et in self.entity_types:
                                if et.lower() == e["type"].lower():
                                    e["type"] = et
                                    break
                        valid_entities.append(e)

                valid_relationships = []
                entity_names = {e["name"] for e in valid_entities}
                for r in relationships:
                    if r.get("source") in entity_names and r.get("target") in entity_names and r.get("relation"):
                        # Normalize relation type
                        if r["relation"] not in self.relation_types:
                            for rt in self.relation_types:
                                if rt.lower() == r["relation"].lower().replace(" ", "_"):
                                    r["relation"] = rt
                                    break
                        valid_relationships.append(r)

                logger.debug(f"Extracted {len(valid_entities)} entities and " f"{len(valid_relationships)} relationships with descriptions")
                return valid_entities, valid_relationships

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
                continue
            except Exception as e:
                logger.warning(f"Extraction error (attempt {attempt + 1}): {e}")
                continue

        return [], []

    @classmethod
    def class_name(cls) -> str:
        """Return the class name for serialization."""
        return "GraphRAGExtractor"


def create_graphrag_extractor(
    llm: Optional[OpenAI] = None,
    entity_types: Optional[List[str]] = None,
    relation_types: Optional[List[str]] = None,
) -> GraphRAGExtractor:
    """
    Factory function to create a GraphRAG extractor.

    Args:
        llm: Language model (defaults to Settings.llm)
        entity_types: Allowed entity types (defaults to ALLOWED_NODES)
        relation_types: Allowed relationship types (defaults to ALLOWED_RELATIONSHIPS)

    Returns:
        Configured GraphRAGExtractor instance
    """
    return GraphRAGExtractor(
        llm=llm,
        entity_types=entity_types,
        relation_types=relation_types,
    )
