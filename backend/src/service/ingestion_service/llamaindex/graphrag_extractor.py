from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence, Tuple

from llama_index.core import Settings
from llama_index.core.graph_stores.types import (
    KG_NODES_KEY,
    KG_RELATIONS_KEY,
    EntityNode,
    Relation,
)
from llama_index.core.schema import BaseNode, TransformComponent
from llama_index.llms.openai import OpenAI

from src.service.ingestion_service.settings import ALLOWED_NODES, ALLOWED_RELATIONSHIPS

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

MIN_TEXT_LENGTH = 50
MAX_TEXT_LENGTH = 4000


class GraphRAGExtractor(TransformComponent):
    def __init__(
        self,
        llm: Optional[OpenAI] = None,
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        max_retries: int = 3,
    ) -> None:
        super().__init__()
        self.llm = llm if llm is not None else Settings.llm
        self.entity_types = entity_types or ALLOWED_NODES
        self.relation_types = relation_types or ALLOWED_RELATIONSHIPS
        self.max_retries = max_retries

    def __call__(self, nodes: Sequence[BaseNode], **kwargs: Any) -> List[BaseNode]:
        for node in nodes:
            try:
                entities, relationships = self._extract_with_descriptions(node)
                self._add_entities_to_node(node, entities)
                self._add_relationships_to_node(node, relationships, entities)
            except Exception:
                continue
        return list(nodes)

    def _add_entities_to_node(self, node: BaseNode, entities: List[dict]) -> None:
        kg_nodes = node.metadata.get(KG_NODES_KEY, [])
        for entity in entities:
            entity_node = EntityNode(
                name=entity["name"],
                label=entity["type"],
                properties={"entity_description": entity.get("description", "")},
            )
            kg_nodes.append(entity_node)
        node.metadata[KG_NODES_KEY] = kg_nodes

    def _add_relationships_to_node(self, node: BaseNode, relationships: List[dict], entities: List[dict]) -> None:
        kg_relations = node.metadata.get(KG_RELATIONS_KEY, [])
        for rel in relationships:
            relation = Relation(
                label=rel["relation"],
                source_id=rel["source"],
                target_id=rel["target"],
                properties={"relationship_description": rel.get("description", "")},
            )
            kg_relations.append(relation)
        node.metadata[KG_RELATIONS_KEY] = kg_relations

    def _extract_with_descriptions(self, node: BaseNode) -> Tuple[List[dict], List[dict]]:
        text = node.get_content()
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            return [], []

        prompt = GRAPHRAG_EXTRACTION_PROMPT.format(
            entity_types=", ".join(self.entity_types),
            relation_types=", ".join(self.relation_types),
            text=text[:MAX_TEXT_LENGTH],
        )

        for attempt in range(self.max_retries):
            try:
                response = self.llm.complete(prompt)
                response_text = self._clean_response(response.text.strip())
                data = json.loads(response_text)
                entities = self._validate_entities(data.get("entities", []))
                relationships = self._validate_relationships(data.get("relationships", []), entities)
                return entities, relationships
            except json.JSONDecodeError:
                continue
            except Exception:
                continue
        return [], []

    def _clean_response(self, response_text: str) -> str:
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            return "\n".join(lines[1:-1])
        return response_text

    def _validate_entities(self, entities: List[dict]) -> List[dict]:
        valid_entities = []
        for e in entities:
            if not e.get("name") or not e.get("type"):
                continue
            if e["type"] not in self.entity_types:
                matched_type = self._match_type_case_insensitive(e["type"], self.entity_types)
                if matched_type:
                    e["type"] = matched_type
            valid_entities.append(e)
        return valid_entities

    def _validate_relationships(self, relationships: List[dict], entities: List[dict]) -> List[dict]:
        entity_names = {e["name"] for e in entities}
        valid_relationships = []
        for r in relationships:
            if r.get("source") not in entity_names:
                continue
            if r.get("target") not in entity_names:
                continue
            if not r.get("relation"):
                continue
            if r["relation"] not in self.relation_types:
                matched_rel = self._match_type_case_insensitive(r["relation"].replace(" ", "_"), self.relation_types)
                if matched_rel:
                    r["relation"] = matched_rel
            valid_relationships.append(r)
        return valid_relationships

    def _match_type_case_insensitive(self, value: str, allowed: List[str]) -> Optional[str]:
        value_lower = value.lower()
        for item in allowed:
            if item.lower() == value_lower:
                return item
        return None

    @classmethod
    def class_name(cls) -> str:
        return "GraphRAGExtractor"


def create_graphrag_extractor(
    llm: Optional[OpenAI] = None,
    entity_types: Optional[List[str]] = None,
    relation_types: Optional[List[str]] = None,
) -> GraphRAGExtractor:
    return GraphRAGExtractor(
        llm=llm,
        entity_types=entity_types,
        relation_types=relation_types,
    )
