from typing import Any, Dict, List

from .base_linker import GraphLinker


class DeduplicationLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        query = """
        MATCH (e:__Entity__)
        WITH e.name as name, collect(e) as nodes
        WHERE size(nodes) > 1
        CALL apoc.refactor.mergeNodes(nodes, {properties: 'combine', mergeRels: true})
        YIELD node
        RETURN count(node) as merged_count
        """
        try:
            result = self._execute_query(query)
            count = result[0]["merged_count"] if result else 0
            return {"merged_count": count}
        except Exception as e:
            return {"error": str(e)}
