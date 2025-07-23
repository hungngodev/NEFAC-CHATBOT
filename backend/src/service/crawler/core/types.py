"""
Common types and data models for the NEFAC crawler.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CrawlerSource(Enum):
    """Enumeration of crawler sources."""

    WORDPRESS_REST_API = "wordpress_rest_api"
    GRAPHQL_API = "graphql_api"
    GRAPHQL_AUTHENTICATED = "graphql_authenticated"
    WEB_SCRAPING = "web_scraping"
    LINK_DISCOVERY = "link_discovery"
    CONTENT_EXTRACTION = "content_extraction"
    SELENIUM_SCRAPER = "selenium_scraper"
    YOUTUBE_CHANNEL = "youtube_channel"


class FileTypeCategory(Enum):
    """Enumeration of file type categories."""

    DOCUMENT = "document"
    IMAGE = "image"
    ARCHIVE = "archive"
    WEB_PAGE = "web_page"
    OTHER = "other"


@dataclass
class DocumentInfo:
    """Information about a discovered document."""

    id: str
    title: str
    source_url: str
    mime_type: str
    date: str
    modified: Optional[str] = None
    alt_text: str = ""
    description: str = ""
    caption: str = ""
    source: str = ""
    file_size: int = 0

    # Additional metadata
    file_path: Optional[str] = None
    filename: Optional[str] = None
    download_date: Optional[str] = None
    processing_timestamp: Optional[float] = None
    crawler_version: str = "3.0"

    # HTTP metadata
    http_status_code: Optional[int] = None
    http_headers: Optional[Dict[str, Any]] = None

    # File classification
    file_extension: Optional[str] = None
    file_type_category: Optional[str] = None
    is_image: bool = False
    is_document: bool = False
    is_archive: bool = False
    validation_status: str = "pending"


@dataclass
class CrawlerStats:
    """Statistics for the crawler run."""

    total_documents: int = 0
    downloaded_documents: int = 0
    failed_downloads: int = 0
    quarantined_documents: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Source statistics
    sources: Dict[str, int] = field(default_factory=lambda: {source.value: 0 for source in CrawlerSource})

    # MIME type statistics
    mime_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class YouTubeVideoInfo:
    """Information about a YouTube video."""

    video_id: str
    title: str
    source_url: str
    description: str = ""
    duration: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    uploader: str = ""
    channel: str = ""
    channel_id: str = ""
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    thumbnail: str = ""
    transcript_available: bool = False
    transcript_file: Optional[str] = None
    transcript_length: int = 0
    transcript_word_count: int = 0


@dataclass
class ExtractorResult:
    """Result from a content extractor."""

    documents: List[DocumentInfo]
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
