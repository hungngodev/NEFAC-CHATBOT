"""Sitemap Navigator Tool for hierarchical website navigation.

This tool fetches and parses WordPress sitemaps to provide:
- Hierarchical page discovery
- Fuzzy search across page titles
- Breadcrumb path generation
- Parent-child relationship traversal
"""

import asyncio
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from langchain_core.tools import tool
from pydantic import Field

from src.schemas.navigation_state import SitemapSearchResult

logger = logging.getLogger(__name__)


class SitemapCache:
    """Cached sitemap data with hierarchical graph structure.

    Fetches and parses WordPress sitemaps, building a hierarchy graph
    for navigation and search operations.
    """

    _instance: Optional["SitemapCache"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._url_map: Dict[str, Dict[str, Any]] = {}  # url -> page data
        self._title_map: Dict[str, str] = {}  # normalized title -> url
        self._hierarchy: Dict[str, List[str]] = {}  # parent url -> child urls
        self._last_fetch: Optional[float] = None
        self._ttl = int(os.getenv("SITEMAP_CACHE_TTL", "3600"))  # 1 hour default
        self._sitemap_url = os.getenv("SITEMAP_URL", "https://nefac.org/sitemap.xml")

    @classmethod
    async def get_instance(cls) -> "SitemapCache":
        """Get or create the singleton cache instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()

            instance = cls._instance
            if instance._last_fetch is None or (time.time() - instance._last_fetch > instance._ttl):
                await instance._fetch_sitemap()

            return instance

    async def _fetch_sitemap(self) -> None:
        """Fetch and parse the WordPress sitemap index and sub-sitemaps."""
        logger.info(f"Fetching sitemap from {self._sitemap_url}")

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                # Fetch sitemap index
                async with session.get(self._sitemap_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to fetch sitemap: HTTP {resp.status}")
                        return
                    index_xml = await resp.text()

                # Parse sitemap index
                root = ET.fromstring(index_xml)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

                # Check if this is a sitemap index or a regular sitemap
                sitemap_locs = root.findall(".//sm:sitemap/sm:loc", ns)

                if sitemap_locs:
                    # It's a sitemap index, fetch each sub-sitemap
                    for loc_elem in sitemap_locs:
                        sub_url = loc_elem.text
                        if sub_url:
                            await self._parse_sub_sitemap(session, sub_url, ns)
                else:
                    # It's a regular sitemap, parse URLs directly
                    await self._parse_urls_from_sitemap(root, ns)

                # Build hierarchy from URL structure
                self._build_hierarchy()

                self._last_fetch = time.time()
                logger.info(f"Sitemap cache loaded: {len(self._url_map)} URLs")

        except Exception as e:
            logger.error(f"Error fetching sitemap: {e}")

    async def _parse_sub_sitemap(self, session: aiohttp.ClientSession, url: str, ns: Dict[str, str]) -> None:
        """Parse a sub-sitemap file."""
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to fetch sub-sitemap {url}: HTTP {resp.status}")
                    return
                xml_content = await resp.text()

            root = ET.fromstring(xml_content)
            await self._parse_urls_from_sitemap(root, ns)

        except Exception as e:
            logger.warning(f"Error parsing sub-sitemap {url}: {e}")

    async def _parse_urls_from_sitemap(self, root: ET.Element, ns: Dict[str, str]) -> None:
        """Extract URLs and metadata from a sitemap XML element."""
        for url_elem in root.findall(".//sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            lastmod = url_elem.find("sm:lastmod", ns)
            priority = url_elem.find("sm:priority", ns)

            if loc is not None and loc.text:
                url = loc.text
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split("/") if p]

                # Generate title from URL path (will be overwritten if we fetch actual titles)
                title = path_parts[-1].replace("-", " ").title() if path_parts else "Home"

                self._url_map[url] = {
                    "url": url,
                    "title": title,
                    "path": parsed.path,
                    "last_modified": lastmod.text if lastmod is not None else None,
                    "priority": float(priority.text) if priority is not None and priority.text is not None else None,
                    "breadcrumb_path": path_parts,
                    "parent_url": None,
                    "children_urls": [],
                }

                # Add to title map for search
                normalized_title = title.lower()
                self._title_map[normalized_title] = url

    def _build_hierarchy(self) -> None:
        """Build parent-child relationships from URL structure."""
        sorted_urls = sorted(self._url_map.keys(), key=lambda u: len(urlparse(u).path))

        for url in sorted_urls:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]

            if len(path_parts) > 1:
                # Find parent by removing last path segment
                parent_path = "/" + "/".join(path_parts[:-1]) + "/"
                parent_url = f"{parsed.scheme}://{parsed.netloc}{parent_path}"

                # Also try without trailing slash
                parent_url_no_slash = parent_url.rstrip("/")

                if parent_url in self._url_map:
                    self._url_map[url]["parent_url"] = parent_url
                    self._url_map[parent_url]["children_urls"].append(url)
                    self._hierarchy.setdefault(parent_url, []).append(url)
                elif parent_url_no_slash in self._url_map:
                    self._url_map[url]["parent_url"] = parent_url_no_slash
                    self._url_map[parent_url_no_slash]["children_urls"].append(url)
                    self._hierarchy.setdefault(parent_url_no_slash, []).append(url)

    def search(self, query: str, max_results: int = 10) -> List[SitemapSearchResult]:
        """Search sitemap by fuzzy matching titles and paths.

        Args:
            query: Search term
            max_results: Maximum number of results to return

        Returns:
            List of matching SitemapSearchResult objects
        """
        if not self._url_map:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_results: List[tuple[float, str]] = []

        for url, data in self._url_map.items():
            title = data.get("title", "").lower()
            path = data.get("path", "").lower()
            breadcrumb = " ".join(data.get("breadcrumb_path", [])).lower()

            # Calculate relevance score
            score = 0.0

            # Exact title match
            if query_lower == title:
                score += 1.0
            elif query_lower in title:
                score += 0.7

            # Word overlap in title
            title_words = set(title.split())
            word_overlap = len(query_words & title_words) / max(len(query_words), 1)
            score += word_overlap * 0.5

            # Path match
            if query_lower in path:
                score += 0.3

            # Breadcrumb match
            if query_lower in breadcrumb:
                score += 0.2

            # Priority boost
            if data.get("priority"):
                score += data["priority"] * 0.1

            if score > 0:
                scored_results.append((score, url))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Convert to SitemapSearchResult objects
        results = []
        for score, url in scored_results[:max_results]:
            data = self._url_map[url]
            results.append(
                SitemapSearchResult(
                    url=url,
                    title=data["title"],
                    last_modified=data.get("last_modified"),
                    parent_url=data.get("parent_url"),
                    children_urls=data.get("children_urls", []),
                    breadcrumb_path=data.get("breadcrumb_path", []),
                    priority=data.get("priority"),
                )
            )

        return results

    def get_hierarchy_context(self, url: str) -> Dict[str, Any]:
        """Get hierarchical context for a URL.

        Returns parent, siblings, and children for navigation.
        """
        if url not in self._url_map:
            return {}

        data = self._url_map[url]
        parent_url = data.get("parent_url")

        context = {
            "current": data,
            "parent": self._url_map.get(parent_url) if parent_url else None,
            "children": [self._url_map[u] for u in data.get("children_urls", []) if u in self._url_map],
            "siblings": [],
        }

        # Get siblings (other children of parent)
        if parent_url and parent_url in self._url_map:
            siblings = [self._url_map[u] for u in self._url_map[parent_url].get("children_urls", []) if u in self._url_map and u != url]
            context["siblings"] = siblings

        return context


@tool
async def sitemap_search(query: str = Field(description="Search term to find pages in the sitemap"), max_results: int = Field(default=10, description="Maximum number of results (1-50)", ge=1, le=50)) -> str:
    """Search the NEFAC website sitemap to discover pages with hierarchical context.

    Use this tool to find pages on the website that match a topic or keyword.
    Returns pages with their breadcrumb paths for navigation context.

    Example queries: 'FOIA', 'First Amendment', 'press freedom'
    """
    cache = await SitemapCache.get_instance()
    results = cache.search(query, max_results)

    if not results:
        return json.dumps({"found": 0, "message": f"No pages found matching '{query}'", "suggestions": ["Try broader search terms", "Check spelling"]}, indent=2)

    # Format results
    formatted = []
    for r in results:
        formatted.append(
            {
                "title": r.title,
                "url": r.url,
                "breadcrumb": " > ".join(["Home"] + r.breadcrumb_path) if r.breadcrumb_path else "Home",
                "last_modified": r.last_modified,
                "has_children": len(r.children_urls) > 0,
                "child_count": len(r.children_urls),
            }
        )

    return json.dumps({"found": len(results), "query": query, "results": formatted}, indent=2)


@tool
async def sitemap_get_hierarchy(url: str = Field(description="URL to get hierarchy context for")) -> str:
    """Get the hierarchical navigation context for a specific URL.

    Returns the parent page, sibling pages, and child pages for navigation.
    Use this to help users explore related content.
    """
    cache = await SitemapCache.get_instance()
    context = cache.get_hierarchy_context(url)

    if not context:
        return json.dumps({"error": f"URL not found in sitemap: {url}", "suggestion": "Use sitemap_search to find valid URLs first"}, indent=2)

    def format_page(data: Dict[str, Any]) -> Dict[str, str]:
        return {"title": data.get("title", "Unknown"), "url": data.get("url", ""), "breadcrumb": " > ".join(["Home"] + data.get("breadcrumb_path", []))}

    result = {
        "current": format_page(context["current"]),
        "parent": format_page(context["parent"]) if context.get("parent") else None,
        "children": [format_page(c) for c in context.get("children", [])],
        "siblings": [format_page(s) for s in context.get("siblings", [])],
    }

    return json.dumps(result, indent=2)
