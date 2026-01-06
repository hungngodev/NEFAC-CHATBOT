"""Navigation state models for the librarian-style resource navigator.

This module defines Pydantic models and TypedDicts for the navigation output system,
replacing the answer-generating research system with a resource discovery approach.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, List, NotRequired, Optional, TypedDict

from langchain_core.documents import Document
from pydantic import BaseModel, Field

###################
# Navigation Structured Outputs
###################


class ResourceCard(BaseModel):
    """A single resource for navigation output.

    Represents a discovered resource with hierarchical context and deep linking.
    The chatbot returns these instead of synthesized answers.
    """

    title: str = Field(description="Resource title")
    url: str = Field(description="Full URL to the resource")
    breadcrumb: str = Field(description="Hierarchical location, e.g., 'Home > Legal Guides > FOIA'")
    snippet: str = Field(description="1-2 sentence description of what the user will find. " "Must NOT interpret or summarize content, only describe what's there.")
    section_link: Optional[str] = Field(default=None, description="Deep link to specific section with anchor, e.g., 'url#section-id'")
    timestamp_link: Optional[str] = Field(default=None, description="Deep link to video timestamp, e.g., 'url&t=120s'")
    relevance_score: float = Field(ge=0.0, le=1.0, description="Relevance score from 0.0 to 1.0")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata: date, author, category, document_type, etc.")
    related_resources: List[str] = Field(default_factory=list, description="List of related resource URLs for further exploration")
    resource_type: str = Field(description="Type of resource: 'page', 'pdf', 'video', 'post', 'document'")


class NavigationSuggestion(BaseModel):
    """A navigation suggestion for further exploration."""

    action: str = Field(description="What to explore, e.g., 'Narrow by state', 'See related topics'")
    query_hint: str = Field(description="Example query to try")
    facet_type: Optional[str] = Field(default=None, description="Facet category if applicable")


class NavigationOutput(BaseModel):
    """Complete navigation output - replaces compressed_research.

    This is the structured output that the navigator agent produces,
    containing discovered resources organized for user exploration.
    """

    resources: List[ResourceCard] = Field(default_factory=list, description="List of discovered resources with hierarchical context")
    navigation_suggestions: List[NavigationSuggestion] = Field(default_factory=list, description="Suggestions for refining or expanding the search")
    hierarchy_context: dict[str, List[str]] = Field(default_factory=dict, description="Site hierarchy context, e.g., {'Legal Guides': ['FOIA', 'First Amendment', ...]}")
    summary_note: str = Field(default="", description="Brief note about what was found (not interpretation of content)")
    total_resources_found: int = Field(default=0, description="Total resources matching query")


class NavigationComplete(BaseModel):
    """Call this tool to indicate that navigation/discovery is complete."""


###################
# Navigation State Definitions
###################


def reduce_resources(current: List[ResourceCard] | None, new: List[ResourceCard] | None | dict) -> List[ResourceCard]:
    """Reducer for aggregating ResourceCards, avoiding duplicates by URL."""
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value", [])

    if current is None:
        current = []
    if new is None:
        new = []

    seen_urls = {r.url for r in current}
    unique = list(current)

    for resource in new:
        if resource.url not in seen_urls:
            seen_urls.add(resource.url)
            unique.append(resource)

    return unique


class NavigatorState(TypedDict):
    """State for the navigator subgraph - mirrors ResearcherState for navigation mode.

    Used when LIBRARIAN_MODE is enabled. Replaces research concepts with navigation.
    """

    # Core navigation fields
    navigator_messages: NotRequired[Annotated[list, operator.add]]
    tool_call_iterations: NotRequired[int]
    discovery_topic: str  # Replaces research_topic
    navigation_output: NotRequired[NavigationOutput]  # Replaces compressed_research

    # Resource tracking
    discovered_resources: NotRequired[Annotated[List[ResourceCard], reduce_resources]]
    raw_notes: NotRequired[Annotated[list[str], operator.add]]
    documents: NotRequired[list[Document]]  # Still useful for internal tracking

    # Hierarchy context for breadcrumb building
    site_hierarchy: NotRequired[dict[str, Any]]
    current_hierarchy_path: NotRequired[List[str]]


class NavigatorOutputState(BaseModel):
    """Output state for navigator - replaces ResearcherOutputState."""

    navigation_output: NavigationOutput
    raw_notes: list[str] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class NavigatorSendOutputState(TypedDict):
    """Output envelope for Send() aggregation from navigation team.

    Mirrors ResearcherSendOutputState for navigator pattern.
    """

    completed_navigation_results: Annotated[List[NavigatorOutputState], operator.add]


###################
# Extended Tool Models
###################


class SitemapSearchResult(BaseModel):
    """Result from sitemap search tool."""

    url: str
    title: str
    last_modified: Optional[str] = None
    parent_url: Optional[str] = None
    children_urls: List[str] = Field(default_factory=list)
    breadcrumb_path: List[str] = Field(default_factory=list)
    priority: Optional[float] = None


class MetadataFilterQuery(BaseModel):
    """Query parameters for metadata-based filtering."""

    filters: dict[str, Any] = Field(description="Metadata filters. Use '__gte', '__lte', '__contains' suffixes for operators. " "Example: {'date__gte': '2023-01-01', 'category__contains': 'FOIA'}")
    return_full_docs: bool = Field(default=False, description="Whether to return full documents or just metadata summaries")
    max_results: int = Field(default=20, ge=1, le=100)


class SectionLinkResult(BaseModel):
    """Result from section linking tool."""

    full_url: str = Field(description="Complete URL with anchor/timestamp")
    section_title: str = Field(description="Title of the linked section")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in section match")
    link_type: str = Field(description="'anchor', 'page', or 'timestamp'")
