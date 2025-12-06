import logging
from typing import Any, Dict, List

from .base_linker import GraphLinker

logger = logging.getLogger(__name__)


class DeduplicationLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        query = """
        MATCH (e:Entity)
        WITH e.name as name, collect(e) as nodes
        WHERE size(nodes) > 1
        CALL apoc.refactor.mergeNodes(nodes, {properties: 'combine', mergeRels: true})
        YIELD node
        RETURN count(node) as merged_count
        """
        try:
            result = self._execute_query(query)
            count = result[0]["merged_count"] if result else 0
            logger.info(f"DeduplicationLinker: Merged {count} entities.")
            return {"merged_count": count}
        except Exception as e:
            logger.error(f"DeduplicationLinker failed: {e}")
            return {"error": str(e)}
