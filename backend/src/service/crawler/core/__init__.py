"""
Core Components for the NEFAC Document Crawler

This module contains the essential core components that form the foundation of the crawler:

1. NEFACCrawler - Main orchestrator that coordinates all crawling activities
2. CrawlerConfig - Centralized configuration management with 80+ environment variables
3. Type Definitions - Comprehensive data models for documents, metadata, and results
4. Deduplication Engine - Advanced content hashing and fuzzy matching for duplicate detection
5. Discovery Engine - Sitemap parsing and URL discovery mechanisms
6. Processors - Core processing pipelines for document handling

The core module provides the backbone infrastructure that all other modules depend on.
"""

from .config import DOCUMENT_TYPES, ENDPOINTS, CrawlerConfig

# from .main_crawler import NEFACCrawler  # Commented out to prevent circular import
from .types import (
    CrawlerSource,
    CrawlerStats,
    DocumentInfo,
    ExtractorResult,
    FileTypeCategory,
    YouTubeVideoInfo,
)

__all__ = [
    # "NEFACCrawler",  # Commented out to prevent circular import - import directly from main_crawler
    "CrawlerConfig",
    "DocumentInfo",
    "CrawlerStats",
    "CrawlerSource",
    "FileTypeCategory",
    "YouTubeVideoInfo",
    "ExtractorResult",
    "ENDPOINTS",
    "DOCUMENT_TYPES",
]
