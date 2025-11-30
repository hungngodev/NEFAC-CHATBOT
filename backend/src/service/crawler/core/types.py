"""
Simplified types for NEFAC crawler with content-specific metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.schemas.metadata import BaseMetadata


class CrawlerSource(Enum):
    """Crawler sources."""

    WORDPRESS_REST_API = "wordpress_rest_api"
    YOUTUBE = "youtube"


@dataclass
class ExtractorResult:
    """Result from content extraction."""

    documents: list[BaseMetadata]  # Can be PDFMetadata, YouTubeMetadata, etc.
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlerStats:
    """Simple crawler statistics."""

    total_documents: int = 0
    failed_downloads: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    sources: dict[str, int] = field(default_factory=dict)
