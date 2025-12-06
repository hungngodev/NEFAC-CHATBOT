import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class GDSUtils:
    def __init__(self, driver):
        self.driver = driver

    def check_gds_availability(self) -> bool:
        query = "RETURN gds.version() AS version"
        try:
            with self.driver.session() as session:
                result = session.run(query).single()
                return bool(result)
        except Exception as e:
            logger.warning(f"GDS not available: {e}")
            return False

    def drop_graph(self, graph_name: str) -> None:
        query = """
        CALL gds.graph.exists($graph_name) YIELD exists
        WHERE exists
        CALL gds.graph.drop($graph_name) YIELD graphName
        RETURN graphName
        """
        with self.driver.session() as session:
            session.run(query, graph_name=graph_name)

    def project_graph(self, graph_name: str, node_projection: Any, relationship_projection: Any) -> None:
        self.drop_graph(graph_name)
        query = """
        CALL gds.graph.project(
            $graph_name,
            $node_projection,
            $relationship_projection
        )
        YIELD graphName, nodeCount, relationshipCount
        """
        with self.driver.session() as session:
            session.run(query, graph_name=graph_name, node_projection=node_projection, relationship_projection=relationship_projection)

    def run_leiden(self, graph_name: str, write_property: str, gamma: float = 1.0) -> Dict[str, Any]:
        query = """
        CALL gds.leiden.write(
            $graph_name,
            {
                writeProperty: $write_property,
                gamma: $gamma
            }
        )
        YIELD communityCount, modularity, communitiesWritten
        RETURN communityCount, modularity, communitiesWritten
        """
        with self.driver.session() as session:
            result = session.run(query, graph_name=graph_name, write_property=write_property, gamma=gamma).single()
            return dict(result) if result else {}
