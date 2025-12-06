import logging
from typing import Any, Dict, List

from .base_linker import GraphLinker

logger = logging.getLogger(__name__)


class TemporalLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        query = """
        MATCH (d:Document)
        WHERE d.id IN $doc_ids AND d.date IS NOT NULL
        WITH d ORDER BY d.date ASC
        WITH collect(d) as docs
        UNWIND range(0, size(docs)-2) as i
        WITH docs[i] as d1, docs[i+1] as d2
        MERGE (d1)-[r:NEXT_IN_TIME]->(d2)
        RETURN count(r) as links_created
        """
        try:
            result = self._execute_query(query, {"doc_ids": document_ids})
            count = result[0]["links_created"] if result else 0
            logger.info(f"TemporalLinker: Created {count} NEXT_IN_TIME links.")
            return {"links_created": count}
        except Exception as e:
            logger.error(f"TemporalLinker failed: {e}")
            return {"error": str(e)}
