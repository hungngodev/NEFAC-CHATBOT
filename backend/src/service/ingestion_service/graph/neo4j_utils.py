"""Neo4j driver utilities for graph operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore


def get_neo4j_driver(graph_store: "Neo4jPropertyGraphStore") -> Any:
    """Extract driver from Neo4jPropertyGraphStore.

    Args:
        graph_store: A Neo4jPropertyGraphStore instance

    Returns:
        The underlying Neo4j driver

    Raises:
        RuntimeError: If driver is not available
    """
    driver = getattr(graph_store, "driver", None) or getattr(graph_store, "_driver", None)
    if driver is None:
        raise RuntimeError("Neo4j driver not available from property graph store")
    return driver
