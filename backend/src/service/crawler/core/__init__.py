"""
Core components for the NEFAC document crawler.

This module contains the main orchestrator, configuration, and type definitions.
"""

from .config import DOCUMENT_TYPES, ENDPOINTS, CrawlerConfig
from .main_crawler import NEFACCrawler
from .types import CrawlerSource, CrawlerStats, DocumentInfo, ExtractorResult, FileTypeCategory, YouTubeVideoInfo

__all__ = [
    "NEFACCrawler",
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
