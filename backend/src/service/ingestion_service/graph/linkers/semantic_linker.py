from typing import Any, Dict, List

from .base_linker import GraphLinker


class SemanticLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        threshold = self.config.get("similarity_threshold", 0.8)
        top_k = self.config.get("top_k", 5)

        query = """
        MATCH (d:Document)
        WHERE d.id IN $doc_ids AND d.embedding IS NOT NULL
        CALL db.index.vector.queryNodes('document_vector_index', $k, d.embedding)
        YIELD node AS similar, score
        WHERE score > $threshold AND similar.id <> d.id
        MERGE (d)-[r:SIMILAR_TO]->(similar)
        ON CREATE SET r.score = score
        RETURN count(r) as links_created
        """

        try:
            result = self._execute_query(query, {"doc_ids": document_ids, "k": top_k, "threshold": threshold})
            count = result[0]["links_created"] if result else 0
            return {"links_created": count}
        except Exception as e:
            return {"error": str(e)}
