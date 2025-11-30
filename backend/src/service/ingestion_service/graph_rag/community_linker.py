import logging
from typing import Any, Dict, List

from .base_linker import GraphLinker
from .gds_utils import GDSUtils

logger = logging.getLogger(__name__)


class CommunityLinker(GraphLinker):
    def __init__(self, driver, config: Dict[str, Any] = None):
        super().__init__(driver, config)
        self.gds = GDSUtils(driver)
        self.graph_name = "document_community_graph"
        self.community_property = "leiden_community"

    def apply_links(self, document_ids: List[str]) -> Dict[str, Any]:
        if not self.gds.check_gds_availability():
            return {"status": "skipped_gds_missing"}

        try:
            self.gds.project_graph(self.graph_name, "Document", {"SIMILAR_TO": {"orientation": "UNDIRECTED"}})

            result = self.gds.run_leiden(self.graph_name, self.community_property, gamma=self.config.get("leiden_gamma", 1.0))

            self._create_community_nodes()
            self.gds.drop_graph(self.graph_name)

            return result
        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return {"error": str(e)}

    def _create_community_nodes(self):
        query = f"""
        MATCH (d:Document)
        WHERE d.{self.community_property} IS NOT NULL
        WITH d, d.{self.community_property} AS community_id
        MERGE (c:Community {{id: community_id}})
        MERGE (d)-[:IN_COMMUNITY]->(c)
        """
        self._execute_query(query)
