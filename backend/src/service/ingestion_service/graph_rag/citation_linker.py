import logging
import re
from typing import Any, Dict, List

from .base_linker import GraphLinker

logger = logging.getLogger(__name__)


class CitationLinker(GraphLinker):
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        links_created = 0
        citation_pattern = r"(\d+)\s+U\.?S\.?\s+(\d+)"

        for doc_id in document_ids:
            try:
                query = "MATCH (d:Document {id: $doc_id}) RETURN d.text as text"
                result = self._execute_query(query, {"doc_id": doc_id})
                if not result or not result[0].get("text"):
                    continue

                text = result[0]["text"]
                matches = re.findall(citation_pattern, text)

                citations = [f"{vol} U.S. {page}" for vol, page in matches]

                if citations:
                    cypher = """
                    MATCH (d:Document {id: $doc_id})
                    UNWIND $citations AS citation_text
                    MERGE (c:Citation {text: citation_text})
                    MERGE (d)-[:CITES]->(c)
                    """
                    self._execute_query(cypher, {"doc_id": doc_id, "citations": citations})
                    links_created += len(citations)
            except Exception as e:
                logger.error(f"CitationLinker error for {doc_id}: {e}")

        return {"links_created": links_created}
