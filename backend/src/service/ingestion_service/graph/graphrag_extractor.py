from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence

from llama_index.core.graph_stores.types import (
    KG_NODES_KEY,
    KG_RELATIONS_KEY,
    EntityNode,
    Relation,
)
from llama_index.core.schema import BaseNode, TransformComponent
from llama_index.llms.openai import OpenAI

from src.service.ingestion_service.observability import log_debug, log_warning
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


class GraphRAGExtractor(TransformComponent):
    def __init__(
        self,
        llm: Optional[OpenAI] = None,
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        max_retries: int = 3,
    ):
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
        for node in nodes:
            try:
                entities, relationships = self._extract_with_descriptions(node)

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
                node_id = node.metadata.get("chunk_id") or node.metadata.get("doc_id") or node.id_
                log_warning("GraphRAG extraction failed", error=e, node_id=str(node_id), stage="graphrag_extraction")
                continue

        return list(nodes)

    def _extract_with_descriptions(self, node: BaseNode) -> tuple[List[dict], List[dict]]:
        text = node.get_content()
        if not text or len(text.strip()) < 50:
            return [], []

        prompt = GRAPHRAG_EXTRACTION_PROMPT.format(
            entity_types=", ".join(self.entity_types),
            relation_types=", ".join(self.relation_types),
            text=text[:4000],
        )

        for attempt in range(self.max_retries):
            try:
                response = self.llm.complete(prompt)
                response_text = response.text.strip()

                if response_text.startswith("```"):
                    lines = response_text.split("\n")
                    response_text = "\n".join(lines[1:-1])

                data = json.loads(response_text)

                entities = data.get("entities", [])
                relationships = data.get("relationships", [])

                valid_entities = []
                for e in entities:
                    if e.get("name") and e.get("type"):
                        if e["type"] not in self.entity_types:
                            for et in self.entity_types:
                                if et.lower() == e["type"].lower():
                                    e["type"] = et
                                    break
                        valid_entities.append(e)

                valid_relationships = []
                entity_names = {e["name"] for e in valid_entities}
                for r in relationships:
                    if r.get("source") in entity_names and r.get("target") in entity_names and r.get("relation"):
                        if r["relation"] not in self.relation_types:
                            for rt in self.relation_types:
                                if rt.lower() == r["relation"].lower().replace(" ", "_"):
                                    r["relation"] = rt
                                    break
                        valid_relationships.append(r)

                return valid_entities, valid_relationships

            except json.JSONDecodeError as e:
                node_id = node.metadata.get("chunk_id") or node.metadata.get("doc_id") or node.id_
                log_debug("JSON parse error", error=e, node_id=str(node_id), extra={"attempt": attempt + 1})
                continue
            except Exception as e:
                node_id = node.metadata.get("chunk_id") or node.metadata.get("doc_id") or node.id_
                log_debug("Extraction error", error=e, node_id=str(node_id), extra={"attempt": attempt + 1})
                continue

        return [], []

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
