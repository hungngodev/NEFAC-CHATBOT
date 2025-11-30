from abc import ABC, abstractmethod
from typing import Any, Dict, List


class GraphLinker(ABC):
    def __init__(self, driver, config: Dict[str, Any] = None):
        self.driver = driver
        self.config = config or {}

    @abstractmethod
    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        pass

    def _execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
