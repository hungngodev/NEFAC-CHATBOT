from typing import Any, Dict, List

from .base_linker import GraphLinker


class EntityCooccurrenceLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        min_weight = self.config.get("cooccurrence_min_weight", 2)

        query = """
        MATCH (d1:Document)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(d2:Document)
        WHERE d1.id IN $doc_ids AND elementId(d1) < elementId(d2)
        WITH d1, d2, count(e) as shared_entities
        WHERE shared_entities >= $min_weight
        MERGE (d1)-[r:RELATED_TO]->(d2)
        ON CREATE SET r.weight = shared_entities, r.type = 'entity_cooccurrence'
        ON MATCH SET r.weight = shared_entities
        RETURN count(r) as links_created
        """
        try:
            result = self._execute_query(query, {"doc_ids": document_ids, "min_weight": min_weight})
            count = result[0]["links_created"] if result else 0
            return {"links_created": count}
        except Exception as e:
            return {"error": str(e)}
