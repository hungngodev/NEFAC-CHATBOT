"""
Extractors package for NEFAC crawler.

This package contains modular extractors for different data sources.
"""

from .graphql_extractor import GraphQLExtractor
from .link_discovery import LinkDiscoveryExtractor
from .selenium_extractor import SeleniumExtractor
from .web_scraper import WebScraperExtractor
from .wordpress import WordPressExtractor
from .youtube_extractor import YouTubeExtractor

__all__ = ["WordPressExtractor", "GraphQLExtractor", "WebScraperExtractor", "YouTubeExtractor", "SeleniumExtractor", "LinkDiscoveryExtractor"]
