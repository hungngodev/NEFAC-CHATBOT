from typing import Any, Dict, List, Optional

from .base_linker import GraphLinker
from .gds_utils import GDSUtils

try:
    import networkx as nx
    from graspologic.partition import hierarchical_leiden

    GRASPOLOGIC_AVAILABLE = True
except ImportError:
    GRASPOLOGIC_AVAILABLE = False


class CommunityLinker(GraphLinker):
    def __init__(self, driver, config: Optional[Dict[str, Any]] = None):
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


class HierarchicalCommunityLinker(GraphLinker):
    def __init__(
        self,
        driver,
        config: Optional[Dict[str, Any]] = None,
        max_cluster_size: int = 10,
        resolution: float = 1.0,
        node_label: str = "__Entity__",
    ):
        super().__init__(driver, config)
        self.max_cluster_size = max_cluster_size
        self.resolution = resolution
        self.node_label = node_label

    def apply_links(self, document_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if not GRASPOLOGIC_AVAILABLE:
            return {"status": "skipped_graspologic_missing", "message": "Install graspologic: pip install graspologic"}

        try:
            G = self._build_networkx_graph()

            if G.number_of_nodes() == 0:
                return {"status": "skipped_empty_graph", "communities_created": 0}

            clusters = hierarchical_leiden(
                G,
                max_cluster_size=self.max_cluster_size,
                resolution=self.resolution,
            )

            levels: Dict[int, Dict[int, List[str]]] = {}
            for item in clusters:
                if item.level not in levels:
                    levels[item.level] = {}
                if item.cluster not in levels[item.level]:
                    levels[item.level][item.cluster] = []
                levels[item.level][item.cluster].append(item.node)

            total_communities = 0
            for level, communities in levels.items():
                for comm_id, members in communities.items():
                    full_comm_id = f"L{level}_C{comm_id}"
                    self._store_community(full_comm_id, level, comm_id, members)
                    total_communities += 1

            return {
                "status": "success",
                "communities_created": total_communities,
                "levels": len(levels),
                "nodes_clustered": G.number_of_nodes(),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _build_networkx_graph(self) -> "nx.Graph":
        query = f"""
        MATCH (e1:{self.node_label})-[r]->(e2:{self.node_label})
        RETURN e1.name as source, e2.name as target,
               type(r) as rel_type, count(*) as weight
        """
        result = self._execute_query(query)

        G = nx.Graph()
        for row in result:
            if row.get("source") and row.get("target"):
                G.add_edge(row["source"], row["target"], weight=row.get("weight", 1), rel_type=row.get("rel_type", "RELATED"))

        return G

    def _store_community(self, full_id: str, level: int, cluster_id: int, members: List[str]):
        query = f"""
        UNWIND $members as member_name
        MATCH (e:{self.node_label} {{name: member_name}})
        SET e.community_level = $level, e.community_id = $cluster_id
        MERGE (c:Community {{id: $full_id}})
        ON CREATE SET c.level = $level, c.cluster_id = $cluster_id
        MERGE (e)-[:IN_COMMUNITY]->(c)
        """
        self._execute_query(
            query,
            {
                "members": members,
                "level": level,
                "cluster_id": cluster_id,
                "full_id": full_id,
            },
        )

    def get_community_stats(self) -> Dict[str, Any]:
        query = """
        MATCH (c:Community)
        OPTIONAL MATCH (c)<-[:IN_COMMUNITY]-(e)
        WITH c.level as level, c.id as community_id, count(e) as member_count
        RETURN level, count(*) as num_communities,
               avg(member_count) as avg_size,
               max(member_count) as max_size
        ORDER BY level
        """
        result = self._execute_query(query)
        return {"levels": list(result)}
