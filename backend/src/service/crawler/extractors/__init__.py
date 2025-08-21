"""
Extractors Package for NEFAC Crawler

MODERN EXTRACTOR ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────────┐
│                      Extractor Hierarchy                           │
│                                                                    │
│  ┌─────────────────┐    ┌────────────────────────────┐             │
│  │   BaseExtractor │◄───┤    Crawl4AIExtractor       │             │
│  │  (Foundation)   │    │   (Unified Web Extractor)  │             │
│  └─────────────────┘    └────────────────────────────┘             │
│          ▲                            ▲                           │
│          │                            │                           │
│  ┌─────────────────┐    ┌────────────────────────────┐             │
│  │ WordPressExtractor│   │ Crawl4AISitemapExtractor  │             │
│  │ (API-based)     │    │ (Sitemap Integration)     │             │
│  └─────────────────┘    └────────────────────────────┘             │
│                                                                    │
│  ┌─────────────────┐                                              │
│  │ GraphQLExtractor│                                              │
│  │ (API-based)     │                                              │
│  └─────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────┘

ARCHITECTURE: Clean modular design with focused responsibilities
- API-based extractors (WordPress, GraphQL) for specialized data sources
- Unified Crawl4AI extractor for AI-powered web content extraction
- Separate modules for schemas, utilities, and processing logic
"""

# Core extractors (preserved)
from .graphql_extractor import GraphQLExtractor
from .wordpress_extractor import WordPressExtractor

# Consolidated AI-powered extractors (deep refactored for maintainability)
# from .crawl4ai_extractor import Crawl4AIExtractor  # Temporarily disabled

# YouTube extractor for comprehensive video content
from .youtube_extractor import YouTubeExtractor

# Comprehensive file extractor for all file types
from .comprehensive_file_extractor import ComprehensiveFileExtractor

# Primary extractors for clean architecture
__all__ = [
    "WordPressExtractor",
    "GraphQLExtractor",
    "Crawl4AIExtractor",
    "Crawl4AISitemapExtractor",
    "YouTubeExtractor",
    "ComprehensiveFileExtractor",
]

# Migration status
__version__ = "4.0-refactored"
__architecture__ = "modular"
