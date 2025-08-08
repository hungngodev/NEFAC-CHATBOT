"""
NEFAC Document Crawler - Modular Version

A comprehensive, modular framework for crawling and extracting documents and content 
from the NEFAC website (nefac.org).

ARCHITECTURE OVERVIEW:
┌─────────────────────────────────────────────────────────────────────────────┐
│  Main Orchestrator                                                          │
│  ┌─────────────────┐                                                       │
│  │  NEFACCrawler   │                                                       │
│  └─────────────────┘                                                       │
│          │                                                                  │
│          ▼                                                                  │
│  ┌─────────────────┐    ┌──────────────────┐    ┌──────────────────────┐   │
│  │   Extractors    │    │   Downloaders    │    │      Utilities       │   │
│  │                 │    │                  │    │                      │   │
│  │ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌──────────────────┐ │   │
│  │ │   GraphQL   │ │    │ │  Document    │ │    │ │   Common Utils   │ │   │
│  │ ├─────────────┤ │    │ │ Downloader   │ │    │ │                  │ │   │
│  │ │  WordPress  │ │    │ ├──────────────┤ │    │ │ ┌──────────────┐ │ │   │
│  │ ├─────────────┤ │    │ │  Metadata    │ │    │ │ │  DateUtils   │ │ │   │
│  │ │   Crawl4AI  │ │    │ │  Manager     │ │    │ │ ├──────────────┤ │ │   │
│  │ │  (Unified)  │ │    │ │              │ │    │ │ │  JSONUtils   │ │ │   │
│  │ └─────────────┘ │    │ └──────────────┘ │    │ │ ├──────────────┤ │ │   │
│  └─────────────────┘    └──────────────────┘    │ │ │ LoggingUtils │ │ │   │
│          │                                       │ └──────────────┘ │ │   │
│          ▼                                       │                  │ │   │
│  ┌─────────────────┐                            │ └──────────────────┘ │   │
│  │    Core         │                            └──────────────────────┘   │
│  │                 │                                                       │
│  │ ┌─────────────┐ │                                                       │
│  │ │  Config     │ │                                                       │
│  │ ├─────────────┤ │                                                       │
│  │ │   Types     │ │                                                       │
│  │ ├─────────────┤ │                                                       │
│  │ │ Deduplication│ │                                                       │
│  │ └─────────────┘ │                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

USAGE:
    from . import NEFACCrawler, CrawlerConfig

    config = CrawlerConfig.from_env_file('.env')
    crawler = NEFACCrawler(config)
    documents = crawler.run_full_crawl()
"""

from .core.config import CrawlerConfig
from .core.main_crawler import NEFACCrawler
from .core.types import CrawlerStats, DocumentInfo, YouTubeVideoInfo

__version__ = "3.0.0"
__all__ = [
    "NEFACCrawler",
    "CrawlerConfig",
    "DocumentInfo",
    "YouTubeVideoInfo",
    "CrawlerStats",
]
