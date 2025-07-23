"""
NEFAC Document Crawler - Modular Version

This package provides a modular, extensible framework for crawling and extracting
documents and content from the NEFAC website (nefac.org).

Key Components:
- NEFACCrawler: Main orchestrator class
- CrawlerConfig: Configuration management  
- Extractors: Modular extractors for different data sources
- Downloaders: File download and metadata management
- Utils: Common utilities and helpers

Usage:
    from crawler import NEFACCrawler, CrawlerConfig

    config = CrawlerConfig.from_env_file('.env')
    crawler = NEFACCrawler(config)
    documents = crawler.run_full_crawl()
"""

from .core.config import CrawlerConfig
from .core.main_crawler import NEFACCrawler
from .core.types import CrawlerStats, DocumentInfo, YouTubeVideoInfo

__version__ = "3.0.0"
__all__ = ["NEFACCrawler", "CrawlerConfig", "DocumentInfo", "YouTubeVideoInfo", "CrawlerStats"]
