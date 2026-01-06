"""Navigation module for librarian-style resource discovery.

This module provides the navigator subgraph that implements the librarian mode,
replacing answer generation with resource navigation and discovery.
"""

from src.core.agents.navigation.navigator import (
    NAVIGATOR_AGENT,
    NAVIGATOR_FORMAT_OUTPUT,
    NAVIGATOR_PACKAGE_OUTPUT,
    NAVIGATOR_TOOLS,
    format_navigation,
    navigator,
    navigator_subgraph,
    navigator_tools,
    package_navigation_output,
)

__all__ = [
    "navigator_subgraph",
    "navigator",
    "navigator_tools",
    "format_navigation",
    "package_navigation_output",
    "NAVIGATOR_AGENT",
    "NAVIGATOR_TOOLS",
    "NAVIGATOR_FORMAT_OUTPUT",
    "NAVIGATOR_PACKAGE_OUTPUT",
]
