"""
Enhanced types and data models for the NEFAC crawler migration.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class CrawlerSource(Enum):
    """Crawler data sources."""

    WORDPRESS_REST_API = "wordpress_rest_api"
    GRAPHQL_API = "graphql_api"
    GRAPHQL_AUTHENTICATED = "graphql_authenticated"
    WEB_SCRAPING = "web_scraping"
    LINK_DISCOVERY = "link_discovery"
    CONTENT_EXTRACTION = "content_extraction"
    SELENIUM_SCRAPER = "selenium_scraper"
    YOUTUBE_CHANNEL = "youtube_channel"
    YOUTUBE = "youtube"
    CRAWL4AI = "crawl4ai"


class FileTypeCategory(Enum):
    """File type categories."""

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
    file_path: Optional[str] = None
    filename: Optional[str] = None
    download_date: Optional[str] = None
    processing_timestamp: Optional[float] = None
    crawler_version: str = "3.0"
    http_status_code: Optional[int] = None
    http_headers: Optional[Dict[str, Any]] = None
    file_extension: Optional[str] = None
    file_type_category: Optional[str] = None
    validation_status: str = "pending"
    content_length: Optional[int] = None
    charset: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Add metadata field


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
    sources: Dict[str, int] = field(
        default_factory=lambda: {source.value: 0 for source in CrawlerSource}
    )

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


# Type aliases for better readability
ExtractionResult = ExtractorResult


# ===== ENHANCED METADATA SCHEMA FOR MIGRATION =====


@dataclass
class SourceMetadata:
    """Track metadata from each extraction source."""

    source_name: str  # 'wordpress', 'graphql', 'crawl4ai'
    extraction_date: datetime
    confidence_score: float
    metadata: Dict[str, Any]
    extraction_method: str
    source_url: str
    processing_time: Optional[float] = None


@dataclass
class SitemapEntry:
    """Entry from sitemap parsing."""

    url: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None
    sitemap_source: str = ""  # Which sitemap file this came from


@dataclass
class URLEntry:
    """URL discovered for processing."""

    url: str
    source: str  # 'sitemap', 'external_link', 'manual'
    priority: int = 0  # Higher = more important
    discovered_date: datetime = field(default_factory=datetime.now)
    parent_url: Optional[str] = None
    content_type_hint: Optional[str] = None

    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        return urlparse(self.url).netloc

    @property
    def is_external(self) -> bool:
        """Check if URL is external to NEFAC."""
        return not self.domain.endswith("nefac.org")


class ContentType(Enum):
    """Enhanced content type classification."""

    DOCUMENT = "document"
    WEB_PAGE = "web_page"
    YOUTUBE_VIDEO = "youtube_video"
    IMAGE = "image"
    ARCHIVE = "archive"
    API_ENDPOINT = "api_endpoint"
    UNKNOWN = "unknown"


@dataclass
class ExtendedDocumentInfo:
    """Enhanced document information with comprehensive metadata."""

    # Core identification
    id: str
    title: str
    url: str
    content_hash: str  # For deduplication

    # Content metadata
    content_type: ContentType = ContentType.UNKNOWN
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    language: Optional[str] = None
    encoding: Optional[str] = None

    # Temporal data
    published_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    crawled_date: datetime = field(default_factory=datetime.now)

    # SEO & Social metadata
    meta_description: Optional[str] = None
    meta_keywords: List[str] = field(default_factory=list)
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_card: Optional[str] = None
    canonical_url: Optional[str] = None

    # Content analysis
    word_count: Optional[int] = None
    reading_time: Optional[int] = None
    content_quality_score: Optional[float] = None
    accessibility_score: Optional[float] = None
    seo_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)

    # Technical metadata
    http_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    checksum: Optional[str] = None

    # NEFAC-specific metadata
    nefac_category: Optional[str] = None
    legal_topic: Optional[str] = None
    jurisdiction: Optional[str] = None
    case_references: List[str] = field(default_factory=list)
    legal_citations: List[str] = field(default_factory=list)

    # Content structure
    keywords: List[str] = field(default_factory=list)

    # Relationships
    outbound_links: List[str] = field(default_factory=list)
    inbound_links: List[str] = field(default_factory=list)
    related_documents: List[str] = field(default_factory=list)
    child_documents: List[str] = field(default_factory=list)
    parent_page: Optional[str] = None  # Added missing field

    # Source tracking
    sources: List[SourceMetadata] = field(default_factory=list)
    extraction_methods: List[str] = field(default_factory=list)

    # File information (consolidated)
    file_path: Optional[str] = None
    filename: Optional[str] = None
    file_extension: Optional[str] = None
    download_date: Optional[datetime] = None
    processing_warnings: List[str] = field(default_factory=list)
    processing_errors: List[str] = field(default_factory=list)

    def generate_content_hash(self, content: str = "") -> str:
        """Generate hash for content-based deduplication."""
        # Use provided content parameter for hashing
        # The content parameter should be passed from the calling code

        # Normalize content for hashing
        normalized_content = content.lower().strip() if content else ""

        # Create composite hash from multiple fields
        hash_components = [
            normalized_content,
            self.title.lower().strip() if self.title else "",
            str(self.file_size) if self.file_size else "",
            self.mime_type or "",
            self.url,
        ]

        composite_string = "|".join(hash_components)
        return hashlib.sha256(composite_string.encode()).hexdigest()

    def add_source_metadata(self, source: SourceMetadata):
        """Add source metadata while avoiding duplicates."""
        # Remove existing metadata from same source
        self.sources = [s for s in self.sources if s.source_name != source.source_name]
        self.sources.append(source)

        # Update extraction methods
        if source.extraction_method not in self.extraction_methods:
            self.extraction_methods.append(source.extraction_method)


@dataclass
class CrawlResult:
    """Result from a complete crawl operation."""

    documents: List[ExtendedDocumentInfo]
    youtube_videos: List[YouTubeVideoInfo] = field(default_factory=list)
    web_content: List[Dict[str, Any]] = field(default_factory=list)

    # Statistics
    total_urls_discovered: int = 0
    total_documents_extracted: int = 0
    duplicates_found: int = 0
    duplicates_merged: int = 0

    # Source breakdown
    wordpress_documents: int = 0
    graphql_documents: int = 0
    crawl4ai_documents: int = 0

    # Quality metrics
    extraction_success_rate: float = 0.0
    metadata_completeness_score: float = 0.0

    # Performance metrics
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None  # seconds
    average_extraction_time: Optional[float] = None  # seconds
    cache_hit_rate: float = 0.0

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def finalize(self):
        """Finalize the crawl result with computed metrics."""
        self.end_time = datetime.now()
        if self.start_time:
            self.total_duration = (self.end_time - self.start_time).total_seconds()

        self.total_documents_extracted = len(self.documents)
        if self.total_urls_discovered > 0:
            self.extraction_success_rate = (
                self.total_documents_extracted / self.total_urls_discovered
            )

        # Calculate metadata completeness
        if self.documents:
            completeness_scores = []
            for doc in self.documents:
                score = self._calculate_completeness_score(doc)
                completeness_scores.append(score)
            self.metadata_completeness_score = sum(completeness_scores) / len(
                completeness_scores
            )

    def _calculate_completeness_score(self, doc: ExtendedDocumentInfo) -> float:
        """Calculate metadata completeness score for a document."""
        total_fields = 0
        filled_fields = 0

        # Core fields (required)
        core_fields = ["title", "url", "content_type", "crawled_date"]
        for field_name in core_fields:
            total_fields += 1
            if getattr(doc, field_name, None):
                filled_fields += 1

        # Optional but valuable fields
        optional_fields = [
            "meta_description",
            "published_date",
            "word_count",
            "topics",
            "entities",
            "sources",
            "mime_type",
            "language",
        ]
        for field_name in optional_fields:
            total_fields += 1
            value = getattr(doc, field_name, None)
            if value and (not isinstance(value, list) or len(value) > 0):
                filled_fields += 1

        return filled_fields / total_fields if total_fields > 0 else 0.0
