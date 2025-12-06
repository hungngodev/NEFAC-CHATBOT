"""
Community detection linkers for the knowledge graph.

Provides two implementations:
- CommunityLinker: Uses Neo4j GDS Leiden algorithm (requires GDS plugin)
- HierarchicalCommunityLinker: Uses graspologic hierarchical Leiden (Python-native)
"""

import logging
from typing import Any, Dict, List, Optional

from .base_linker import GraphLinker
from .gds_utils import GDSUtils

logger = logging.getLogger(__name__)

# Try to import graspologic, but don't fail if not available
try:
    import networkx as nx
    from graspologic.partition import hierarchical_leiden

    GRASPOLOGIC_AVAILABLE = True
except ImportError:
    GRASPOLOGIC_AVAILABLE = False
    logger.info("graspologic not installed. HierarchicalCommunityLinker will not be available.")


class CommunityLinker(GraphLinker):
    """Community detection using Neo4j GDS Leiden algorithm."""

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


class HierarchicalCommunityLinker(GraphLinker):
    """
    Community detection using graspologic's hierarchical Leiden algorithm.

    This provides multi-level community detection, creating nested communities
    that can be used for both local (entity-level) and global (community-level) search.

    Requires: pip install graspologic networkx
    """

    def __init__(
        self,
        driver,
        config: Optional[Dict[str, Any]] = None,
        max_cluster_size: int = 10,
        resolution: float = 1.0,
        node_label: str = "__Entity__",
    ):
        """
        Initialize the hierarchical community linker.

        Args:
            driver: Neo4j driver
            config: Configuration dictionary
            max_cluster_size: Maximum size for each community cluster
            resolution: Resolution parameter for Leiden (higher = more communities)
            node_label: Label of nodes to cluster (default: __Entity__)
        """
        super().__init__(driver, config)
        self.max_cluster_size = max_cluster_size
        self.resolution = resolution
        self.node_label = node_label

    def apply_links(self, document_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Apply hierarchical community detection to the graph.

        Args:
            document_ids: Optional list of document IDs (not used, kept for interface compatibility)

        Returns:
            Dictionary with community detection results
        """
        if not GRASPOLOGIC_AVAILABLE:
            return {"status": "skipped_graspologic_missing", "message": "Install graspologic: pip install graspologic"}

        try:
            # Build NetworkX graph from Neo4j
            G = self._build_networkx_graph()

            if G.number_of_nodes() == 0:
                return {"status": "skipped_empty_graph", "communities_created": 0}

            logger.info(f"Running hierarchical Leiden on {G.number_of_nodes()} nodes, " f"{G.number_of_edges()} edges")

            # Run hierarchical Leiden
            clusters = hierarchical_leiden(
                G,
                max_cluster_size=self.max_cluster_size,
                resolution=self.resolution,
            )

            # Group by community at each level
            levels: Dict[int, Dict[int, List[str]]] = {}
            for item in clusters:
                if item.level not in levels:
                    levels[item.level] = {}
                if item.cluster not in levels[item.level]:
                    levels[item.level][item.cluster] = []
                levels[item.level][item.cluster].append(item.node)

            # Store in Neo4j with hierarchy
            total_communities = 0
            for level, communities in levels.items():
                for comm_id, members in communities.items():
                    full_comm_id = f"L{level}_C{comm_id}"
                    self._store_community(full_comm_id, level, comm_id, members)
                    total_communities += 1

            logger.info(f"Created {total_communities} communities across {len(levels)} levels")

            return {
                "status": "success",
                "communities_created": total_communities,
                "levels": len(levels),
                "nodes_clustered": G.number_of_nodes(),
            }

        except Exception as e:
            logger.error(f"Hierarchical community detection failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _build_networkx_graph(self) -> "nx.Graph":
        """
        Export Neo4j entity graph to NetworkX for community detection.

        Returns:
            NetworkX Graph with entities as nodes and relationships as edges
        """
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
        """
        Store a community and its members in Neo4j.

        Args:
            full_id: Full community ID (e.g., "L0_C1")
            level: Hierarchy level
            cluster_id: Cluster ID within the level
            members: List of entity names in this community
        """
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
        """
        Get statistics about the communities in the graph.

        Returns:
            Dictionary with community statistics
        """
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
