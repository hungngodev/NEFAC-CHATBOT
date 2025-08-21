"""
Enhanced configuration management for the NEFAC crawler migration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from dotenv import load_dotenv

# Base configuration
BASE_URL = "https://nefac.org"
DEFAULT_OUTPUT_DIR = "src/service/crawler/nefac_documents"
CRAWLER_VERSION = "4.0-migration"

# Enhanced API endpoints
ENDPOINTS = {
    "posts": f"{BASE_URL}/wp-json/wp/v2/posts",
    "media": f"{BASE_URL}/wp-json/wp/v2/media",
    "news": f"{BASE_URL}/wp-json/wp/v2/news",
    "graphql": f"{BASE_URL}/graphql",
    "sitemap": f"{BASE_URL}/wp-sitemap.xml",
    "sitemap_index": f"{BASE_URL}/wp-sitemap.xml",
}

# Migration-specific configuration
MIGRATION_CONFIG = {
    "enable_sitemap_discovery": True,
    "enable_external_crawling": True,
    "enable_deduplication": True,
    "enable_metadata_merging": True,
    "enable_crawl4ai": True,
    "enable_parallel_extraction": True,
    "enable_youtube_integration": True,
    "enable_comprehensive_crawling": True,
}

# Document types mapping
DOCUMENT_TYPES: Dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/msword": "doc",
    "application/vnd.ms-excel": "xls",
    "application/vnd.ms-powerpoint": "ppt",
    "text/csv": "csv",
    "text/plain": "txt",
}

# File extensions
DOCUMENT_EXTENSIONS: Set[str] = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".txt",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
}

IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}

ARCHIVE_EXTENSIONS: Set[str] = {".zip", ".rar", ".7z", ".tar", ".gz"}

# Directory structure - File type specific organization
OUTPUT_DIRECTORIES = [
    "youtube",  # YouTube videos + transcripts
    "html",  # Web pages/HTML content
    "pdf",  # PDF documents
    "docx",  # Word documents
    "doc",  # Legacy Word documents
    "xlsx",  # Excel spreadsheets
    "xls",  # Legacy Excel files
    "pptx",  # PowerPoint presentations
    "ppt",  # Legacy PowerPoint files
    "csv",  # CSV files
    "txt",  # Text files
    "rtf",  # Rich text files
    "odt",  # OpenDocument text
    "ods",  # OpenDocument spreadsheet
    "odp",  # OpenDocument presentation
    "images",  # Image files (jpg, png, gif, etc.)
    "archives",  # Compressed files (zip, rar, etc.)
    "metadata",  # Metadata files
    "quarantine",  # Invalid/corrupted files
    "other",  # Unknown/other file types
]

# File extension to directory mapping
FILE_TYPE_DIRECTORIES = {
    # Documents
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".csv": "csv",
    ".txt": "txt",
    ".rtf": "rtf",
    ".odt": "odt",
    ".ods": "ods",
    ".odp": "odp",
    # Images
    ".jpg": "images",
    ".jpeg": "images",
    ".png": "images",
    ".gif": "images",
    ".bmp": "images",
    ".tiff": "images",
    ".tif": "images",
    ".svg": "images",
    ".webp": "images",
    # Archives
    ".zip": "archives",
    ".rar": "archives",
    ".7z": "archives",
    ".tar": "archives",
    ".gz": "archives",
    ".bz2": "archives",
    # Web content
    ".html": "html",
    ".htm": "html",
    ".xml": "html",
    ".json": "html",
}

# Rate limiting and timeouts
DEFAULT_REQUEST_TIMEOUT = 60
DEFAULT_DOWNLOAD_TIMEOUT = 120
DEFAULT_PAGE_DELAY = 0.1
DEFAULT_YOUTUBE_DELAY = 5.0

# Pagination settings
DEFAULT_PER_PAGE = 200
MAX_RETRY_ATTEMPTS = 5

# YouTube configuration
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@nefac"


@dataclass
class YouTubeConfig:
    """Dedicated YouTube configuration with rate limiting and API settings."""

    # Basic YouTube settings
    enabled: bool = True
    channel_url: str = YOUTUBE_CHANNEL_URL
    max_videos: int = 9999
    enable_transcripts: bool = True
    enable_metadata_extraction: bool = True

    # Rate limiting (YouTube is strict about this) - CAUTIOUSLY AGGRESSIVE
    request_delay: float = 5.0
    max_concurrent: int = 2
    batch_size: int = 5
    retry_delay: float = 60.0
    max_retries: int = 3

    # API and proxy settings
    api_key: Optional[str] = None
    use_proxy: bool = False
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    rotating_proxy: Optional[str] = None
    webshare_username: Optional[str] = None
    webshare_password: Optional[str] = None

    # Content filtering
    min_duration_seconds: int = 10
    max_duration_seconds: int = 28800
    skip_live_streams: bool = False
    skip_shorts: bool = False

    # Quality settings
    transcript_language: str = "en"
    fallback_languages: List[str] = field(default_factory=lambda: ["en-US", "en-GB"])
    extract_chapters: bool = True
    extract_comments: bool = True

    # Output organization
    output_subdir: str = "youtube"
    save_thumbnails: bool = True
    save_metadata: bool = True

    # Error handling
    timeout_seconds: int = 300
    continue_on_error: bool = True
    log_failed_videos: bool = True


@dataclass
class CrawlerConfig:
    """Enhanced configuration for the NEFAC crawler migration."""

    # Core settings
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    download_files: bool = True
    wordpress_base_url: str = BASE_URL

    # Migration features
    enable_sitemap_discovery: bool = True
    enable_external_crawling: bool = True
    enable_deduplication: bool = True
    enable_metadata_merging: bool = True
    enable_crawl4ai: bool = True
    enable_parallel_extraction: bool = True
    enable_youtube_integration: bool = True
    enable_comprehensive_crawling: bool = True

    # Crawl4AI configuration - MAXIMIZED FOR SPEED
    crawl4ai_batch_size: int = 50
    crawl4ai_max_concurrent: int = 10
    crawl4ai_content_threshold: float = 0.40
    crawl4ai_enable_caching: bool = True
    crawl4ai_timeout: int = 120
    enable_ai_analysis: bool = True
    content_quality_threshold: float = 0.6

    # Sitemap configuration - MAXIMIZED FOR COMPREHENSIVE CRAWLING
    sitemap_max_urls_per_type: int = 99999
    sitemap_max_total_urls: int = 999999
    sitemap_priority_threshold: float = 0.0
    sitemap_url: str = ENDPOINTS["sitemap"]
    sitemap_cache_ttl: int = 7200
    sitemap_timeout: int = 60
    enable_comprehensive_sitemap_crawl: bool = True

    # Deduplication settings
    content_similarity_threshold: float = 0.92
    enable_url_normalization: bool = True
    enable_content_deduplication: bool = True
    fuzzy_similarity_threshold: float = 0.80
    enable_content_hashing: bool = True

    # External crawling
    external_domain_whitelist: List[str] = field(
        default_factory=lambda: [
            "supremecourt.gov",
            "congress.gov",
            "law.cornell.edu",
            "justia.com",
            "courtlistener.com",
            "govinfo.gov",
            "regulations.gov",
        ]
    )
    max_external_depth: int = 3
    external_crawl_limit: int = 200

    # YouTube configuration - Use dedicated YouTubeConfig
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)

    # Metadata merging
    source_priorities: Dict[str, int] = field(
        default_factory=lambda: {
            "graphql": 100,
            "wordpress": 80,
            "crawl4ai": 60,
            "selenium": 40,
            "web_scraper": 30,
            "link_discovery": 20,
        }
    )

    # Authentication
    crawl4ai_api_key: Optional[str] = None
    crawl4ai_model: str = "gpt-4"
    faust_username: Optional[str] = None
    faust_password: Optional[str] = None
    faust_key: Optional[str] = None
    graphql_token: Optional[str] = None
    webshare_username: Optional[str] = None
    webshare_password: Optional[str] = None

    # Performance settings - MAXIMIZED FOR SPEED
    performance_settings: dict = field(
        default_factory=lambda: {
            "max_concurrent_sources": 10,
            "enable_aggressive_caching": True,
            "processing_timeout": 600,
            "request_timeout": DEFAULT_REQUEST_TIMEOUT,
            "download_timeout": DEFAULT_DOWNLOAD_TIMEOUT,
            "request_delay": 0.05,
            "max_workers": 50,
            "max_concurrent_requests": 200,
            "batch_size": 200,
            "enable_caching": True,
            "cache_ttl": 7200,
            "max_retries": MAX_RETRY_ATTEMPTS,
            "retry_backoff_factor": 2.0,
            "retry_on_status": [429, 500, 502, 503, 504],
        }
    )

    # Content filtering
    content_filtering: dict = field(
        default_factory=lambda: {
            "document_types": None,
            "skip_web_scraping": False,
            "metadata_only": False,
            "min_content_length": 100,
            "max_file_size": 100 * 1024 * 1024,
        }
    )

    # Logging and monitoring
    logging_and_monitoring: dict = field(
        default_factory=lambda: {
            "log_level": "INFO",
            "enable_statistics": True,
            "enable_progress_tracking": True,
            "statistics_interval": 100,
        }
    )

    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Ensure output_dir is a Path object
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

        # Create only the main output directory, not subdirectories
        # Subdirectories will be created on-demand when files are actually saved
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "CrawlerConfig":
        """Load enhanced configuration from environment file."""
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)

        # Parse external domain whitelist
        external_domains = os.getenv("EXTERNAL_DOMAIN_WHITELIST", "")
        domain_list = (
            [d.strip() for d in external_domains.split(",") if d.strip()]
            if external_domains
            else [
                "supremecourt.gov",
                "congress.gov",
                "law.cornell.edu",
                "justia.com",
                "courtlistener.com",
                "govinfo.gov",
                "regulations.gov",
            ]
        )

        # Parse source priorities
        source_priorities = {
            "graphql": int(os.getenv("GRAPHQL_PRIORITY", "100")),
            "wordpress": int(os.getenv("WORDPRESS_PRIORITY", "80")),
            "crawl4ai": int(os.getenv("CRAWL4AI_PRIORITY", "60")),
            "selenium": int(os.getenv("SELENIUM_PRIORITY", "40")),
            "web_scraper": int(os.getenv("WEB_SCRAPER_PRIORITY", "30")),
            "link_discovery": int(os.getenv("LINK_DISCOVERY_PRIORITY", "20")),
        }

        # Parse retry status codes
        retry_codes = os.getenv("RETRY_ON_STATUS", "429,500,502,503,504")
        retry_status_list = [
            int(code.strip())
            for code in retry_codes.split(",")
            if code.strip().isdigit()
        ]

        # Parse performance settings from env
        performance_settings = {
            "max_concurrent_sources": int(os.getenv("MAX_CONCURRENT_SOURCES", "3")),
            "enable_aggressive_caching": os.getenv(
                "ENABLE_AGGRESSIVE_CACHING", "true"
            ).lower()
            == "true",
            "processing_timeout": int(os.getenv("PROCESSING_TIMEOUT", "300")),
            "request_timeout": int(
                os.getenv("REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT))
            ),
            "download_timeout": int(
                os.getenv("DOWNLOAD_TIMEOUT", str(DEFAULT_DOWNLOAD_TIMEOUT))
            ),
            "request_delay": float(os.getenv("REQUEST_DELAY", str(DEFAULT_PAGE_DELAY))),
            "max_workers": int(os.getenv("MAX_WORKERS", "10")),
            "max_concurrent_requests": int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
            "batch_size": int(os.getenv("BATCH_SIZE", "50")),
            "enable_caching": os.getenv("ENABLE_CACHING", "true").lower() == "true",
            "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),
            "max_retries": int(os.getenv("MAX_RETRIES", str(MAX_RETRY_ATTEMPTS))),
            "retry_backoff_factor": float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0")),
            "retry_on_status": retry_status_list,
        }

        # Parse YouTube configuration from env
        youtube_config = YouTubeConfig(
            enabled=os.getenv("YOUTUBE_ENABLED", "true").lower() == "true",
            channel_url=os.getenv("YOUTUBE_CHANNEL_URL", YOUTUBE_CHANNEL_URL),
            max_videos=int(os.getenv("YOUTUBE_MAX_VIDEOS", "1000")),
            enable_transcripts=os.getenv("YOUTUBE_ENABLE_TRANSCRIPTS", "true").lower()
            == "true",
            enable_metadata_extraction=os.getenv(
                "YOUTUBE_ENABLE_METADATA", "true"
            ).lower()
            == "true",
            # Rate limiting
            request_delay=float(os.getenv("YOUTUBE_REQUEST_DELAY", "10.0")),
            max_concurrent=int(os.getenv("YOUTUBE_MAX_CONCURRENT", "1")),
            batch_size=int(os.getenv("YOUTUBE_BATCH_SIZE", "1")),
            retry_delay=float(os.getenv("YOUTUBE_RETRY_DELAY", "30.0")),
            max_retries=int(os.getenv("YOUTUBE_MAX_RETRIES", "3")),
            # API and proxy settings
            api_key=os.getenv("YOUTUBE_API_KEY"),
            use_proxy=os.getenv("YOUTUBE_USE_PROXY", "false").lower() == "true",
            http_proxy=os.getenv("YOUTUBE_HTTP_PROXY"),
            https_proxy=os.getenv("YOUTUBE_HTTPS_PROXY"),
            rotating_proxy=os.getenv("YOUTUBE_ROTATING_PROXY"),
            webshare_username=os.getenv("YOUTUBE_WEBSHARE_USERNAME"),
            webshare_password=os.getenv("YOUTUBE_WEBSHARE_PASSWORD"),
            # Content filtering
            min_duration_seconds=int(os.getenv("YOUTUBE_MIN_DURATION", "30")),
            max_duration_seconds=int(os.getenv("YOUTUBE_MAX_DURATION", "14400")),
            skip_live_streams=os.getenv("YOUTUBE_SKIP_LIVE", "true").lower() == "true",
            skip_shorts=os.getenv("YOUTUBE_SKIP_SHORTS", "false").lower() == "true",
            # Quality settings
            transcript_language=os.getenv("YOUTUBE_TRANSCRIPT_LANG", "en"),
            extract_chapters=os.getenv("YOUTUBE_EXTRACT_CHAPTERS", "true").lower()
            == "true",
            extract_comments=os.getenv("YOUTUBE_EXTRACT_COMMENTS", "false").lower()
            == "true",
            # Output organization
            output_subdir=os.getenv("YOUTUBE_OUTPUT_SUBDIR", "youtube"),
            save_thumbnails=os.getenv("YOUTUBE_SAVE_THUMBNAILS", "true").lower()
            == "true",
            save_metadata=os.getenv("YOUTUBE_SAVE_METADATA", "true").lower() == "true",
            # Error handling
            timeout_seconds=int(os.getenv("YOUTUBE_TIMEOUT", "120")),
            continue_on_error=os.getenv("YOUTUBE_CONTINUE_ON_ERROR", "true").lower()
            == "true",
            log_failed_videos=os.getenv("YOUTUBE_LOG_FAILED", "true").lower() == "true",
        )

        # Parse content filtering settings from env
        content_filtering = {
            "document_types": os.getenv("DOCUMENT_TYPES"),
            "skip_web_scraping": os.getenv("SKIP_WEB_SCRAPING", "false").lower()
            == "true",
            "metadata_only": os.getenv("METADATA_ONLY", "false").lower() == "true",
            "min_content_length": int(os.getenv("MIN_CONTENT_LENGTH", "100")),
            "max_file_size": int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024))),
        }

        # Parse logging settings from env
        logging_and_monitoring = {
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "enable_statistics": os.getenv("ENABLE_STATISTICS", "true").lower()
            == "true",
            "enable_progress_tracking": os.getenv(
                "ENABLE_PROGRESS_TRACKING", "true"
            ).lower()
            == "true",
            "statistics_interval": int(os.getenv("STATISTICS_INTERVAL", "100")),
        }

        return cls(
            # Core settings
            output_dir=Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
            download_files=os.getenv("DOWNLOAD_FILES", "true").lower() == "true",
            wordpress_base_url=os.getenv("WORDPRESS_BASE_URL", BASE_URL),
            # Migration features
            enable_sitemap_discovery=os.getenv(
                "ENABLE_SITEMAP_DISCOVERY", "true"
            ).lower()
            == "true",
            enable_external_crawling=os.getenv(
                "ENABLE_EXTERNAL_CRAWLING", "true"
            ).lower()
            == "true",
            enable_deduplication=os.getenv("ENABLE_DEDUPLICATION", "true").lower()
            == "true",
            enable_metadata_merging=os.getenv("ENABLE_METADATA_MERGING", "true").lower()
            == "true",
            enable_crawl4ai=os.getenv("ENABLE_CRAWL4AI", "true").lower() == "true",
            enable_parallel_extraction=os.getenv(
                "ENABLE_PARALLEL_EXTRACTION", "true"
            ).lower()
            == "true",
            enable_youtube_integration=os.getenv(
                "ENABLE_YOUTUBE_INTEGRATION", "true"
            ).lower()
            == "true",
            enable_comprehensive_crawling=os.getenv(
                "ENABLE_COMPREHENSIVE_CRAWLING", "true"
            ).lower()
            == "true",
            # Crawl4AI configuration
            crawl4ai_batch_size=int(os.getenv("CRAWL4AI_BATCH_SIZE", "10")),
            crawl4ai_max_concurrent=int(os.getenv("CRAWL4AI_MAX_CONCURRENT", "3")),
            crawl4ai_content_threshold=float(
                os.getenv("CRAWL4AI_CONTENT_THRESHOLD", "0.48")
            ),
            crawl4ai_enable_caching=os.getenv("CRAWL4AI_ENABLE_CACHING", "true").lower()
            == "true",
            crawl4ai_timeout=int(os.getenv("CRAWL4AI_TIMEOUT", "60")),
            enable_ai_analysis=os.getenv("ENABLE_AI_ANALYSIS", "true").lower()
            == "true",
            content_quality_threshold=float(
                os.getenv("CONTENT_QUALITY_THRESHOLD", "0.7")
            ),
            # Sitemap configuration
            sitemap_max_urls_per_type=int(
                os.getenv("SITEMAP_MAX_URLS_PER_TYPE", "100")
            ),
            sitemap_max_total_urls=int(os.getenv("SITEMAP_MAX_TOTAL_URLS", "300")),
            sitemap_priority_threshold=float(
                os.getenv("SITEMAP_PRIORITY_THRESHOLD", "0.5")
            ),
            sitemap_url=os.getenv("SITEMAP_URL", ENDPOINTS["sitemap"]),
            sitemap_cache_ttl=int(os.getenv("SITEMAP_CACHE_TTL", "3600")),
            sitemap_timeout=int(os.getenv("SITEMAP_TIMEOUT", "30")),
            # Deduplication settings
            content_similarity_threshold=float(
                os.getenv("CONTENT_SIMILARITY_THRESHOLD", "0.95")
            ),
            enable_url_normalization=os.getenv(
                "ENABLE_URL_NORMALIZATION", "true"
            ).lower()
            == "true",
            enable_content_deduplication=os.getenv(
                "ENABLE_CONTENT_DEDUPLICATION", "true"
            ).lower()
            == "true",
            fuzzy_similarity_threshold=float(
                os.getenv("FUZZY_SIMILARITY_THRESHOLD", "0.85")
            ),
            enable_content_hashing=os.getenv("ENABLE_CONTENT_HASHING", "true").lower()
            == "true",
            # External crawling
            external_domain_whitelist=domain_list,
            max_external_depth=int(os.getenv("MAX_EXTERNAL_DEPTH", "2")),
            external_crawl_limit=int(os.getenv("EXTERNAL_CRAWL_LIMIT", "100")),
            # Metadata merging
            source_priorities=source_priorities,
            # Authentication
            crawl4ai_api_key=os.getenv("CRAWL4AI_API_KEY"),
            crawl4ai_model=os.getenv("CRAWL4AI_MODEL", "gpt-4"),
            faust_username=os.getenv("FAUST_USERNAME"),
            faust_password=os.getenv("FAUST_PASSWORD"),
            faust_key=os.getenv("FAUST_SECRET_KEY"),
            graphql_token=os.getenv("GRAPHQL_TOKEN"),
            webshare_username=os.getenv("WEBSHARE_USERNAME"),
            webshare_password=os.getenv("WEBSHARE_PASSWORD"),
            # Use properly structured dictionaries for nested settings
            performance_settings=performance_settings,
            content_filtering=content_filtering,
            logging_and_monitoring=logging_and_monitoring,
            # YouTube configuration
            youtube=youtube_config,
        )

    def validate(self):
        """Validate configuration settings."""
        validations = [
            (self.wordpress_base_url, "WordPress base URL is required"),
            (self.output_dir, "Output directory is required"),
            (
                self.performance_settings.get("max_workers", 1) >= 1,
                "Max workers must be at least 1",
            ),
            (
                self.performance_settings.get("request_delay", 0) >= 0,
                "Request delay cannot be negative",
            ),
            (
                self.performance_settings.get("request_timeout", 1) > 0,
                "Request timeout must be positive",
            ),
            (
                self.performance_settings.get("download_timeout", 1) > 0,
                "Download timeout must be positive",
            ),
            # YouTube-specific validations
            (
                self.youtube.request_delay >= 0,
                "YouTube request delay cannot be negative",
            ),
            (
                self.youtube.max_concurrent >= 1,
                "YouTube max concurrent must be at least 1",
            ),
            (self.youtube.batch_size >= 1, "YouTube batch size must be at least 1"),
            (self.youtube.timeout_seconds > 0, "YouTube timeout must be positive"),
            (self.youtube.max_retries >= 0, "YouTube max retries cannot be negative"),
            (
                self.youtube.min_duration_seconds >= 0,
                "YouTube min duration cannot be negative",
            ),
            (
                self.youtube.max_duration_seconds > self.youtube.min_duration_seconds,
                "YouTube max duration must be greater than min duration",
            ),
        ]

        for condition, error_msg in validations:
            if not condition:
                raise ValueError(error_msg)

    # Convenience properties for backward compatibility
    @property
    def request_timeout(self) -> int:
        """Request timeout from performance settings."""
        return self.performance_settings.get("request_timeout", DEFAULT_REQUEST_TIMEOUT)

    @property
    def download_timeout(self) -> int:
        """Download timeout from performance settings."""
        return self.performance_settings.get(
            "download_timeout", DEFAULT_DOWNLOAD_TIMEOUT
        )

    @property
    def max_workers(self) -> int:
        """Max workers from performance settings."""
        return self.performance_settings.get("max_workers", 10)

    @property
    def max_concurrent_requests(self) -> int:
        """Max concurrent requests from performance settings."""
        return self.performance_settings.get("max_concurrent_requests", 10)

    @property
    def batch_size(self) -> int:
        """Batch size from performance settings."""
        return self.performance_settings.get("batch_size", 50)

    @property
    def request_delay(self) -> float:
        """Request delay from performance settings."""
        return self.performance_settings.get("request_delay", DEFAULT_PAGE_DELAY)

    @property
    def max_retries(self) -> int:
        """Max retries from performance settings."""
        return self.performance_settings.get("max_retries", MAX_RETRY_ATTEMPTS)

    @property
    def min_content_length(self) -> int:
        """Min content length from content filtering."""
        return self.content_filtering.get("min_content_length", 100)

    @property
    def max_file_size(self) -> int:
        """Max file size from content filtering."""
        return self.content_filtering.get("max_file_size", 100 * 1024 * 1024)

    @property
    def log_level(self) -> str:
        """Log level from logging settings."""
        return self.logging_and_monitoring.get("log_level", "INFO")

    @property
    def max_items_per_source(self) -> int:
        """Max items per source (derived from batch_size)."""
        return self.batch_size * 2  # Allow up to 2 batches per source

    @property
    def base_url(self) -> str:
        """Base URL (alias for wordpress_base_url)."""
        return self.wordpress_base_url

    @property
    def per_page(self) -> int:
        """Items per page for pagination."""
        return min(self.batch_size, DEFAULT_PER_PAGE)

    def save_all_metadata(self) -> bool:
        """Whether to save all metadata (inverse of metadata_only)."""
        return not self.content_filtering.get("metadata_only", False)
