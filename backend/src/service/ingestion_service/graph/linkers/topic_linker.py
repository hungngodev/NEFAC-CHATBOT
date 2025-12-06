import json
import logging
from typing import Any, Dict, List, Optional

from llama_index.core.llms import LLM

from .base_linker import GraphLinker

logger = logging.getLogger(__name__)


class TopicLinker(GraphLinker):
    def __init__(self, driver, config: Optional[Dict[str, Any]] = None, llm: Optional[LLM] = None):
        super().__init__(driver, config)
        self.llm = llm
        if not self.llm:
            from llama_index.core import Settings

            self.llm = Settings.llm

        self.prompt_template = "Extract 3 to 5 key topics from the text. Return ONLY JSON array of strings. " "Text: {text}"

    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        if not self.llm:
            return {"status": "skipped_no_llm"}

        links_created = 0
        for doc_id in document_ids:
            try:
                query = "MATCH (d:Document {id: $doc_id}) RETURN d.text as text"
                result = self._execute_query(query, {"doc_id": doc_id})
                if not result or not result[0].get("text"):
                    continue

                text = result[0]["text"][:4000]
                response = self.llm.complete(self.prompt_template.format(text=text)).text

                cleaned = response.replace("```json", "").replace("```", "").strip()
                topics = json.loads(cleaned)

                if topics:
                    cypher = """
                    MATCH (d:Document {id: $doc_id})
                    UNWIND $topics AS topic_name
                    MERGE (t:Topic {name: topic_name})
                    MERGE (d)-[:DISCUSSES]->(t)
                    """
                    self._execute_query(cypher, {"doc_id": doc_id, "topics": topics})
                    links_created += len(topics)
            except Exception as e:
                logger.error(f"TopicLinker error for {doc_id}: {e}")

        return {"links_created": links_created}
