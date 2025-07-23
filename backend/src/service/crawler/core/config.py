"""
Configuration management for the NEFAC crawler.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

from dotenv import load_dotenv

# Base configuration
BASE_URL = "https://nefac.org"
DEFAULT_OUTPUT_DIR = "nefac_documents"
CRAWLER_VERSION = "3.0"

# API endpoints
ENDPOINTS = {
    "posts": f"{BASE_URL}/wp-json/wp/v2/posts",
    "media": f"{BASE_URL}/wp-json/wp/v2/media",
    "news": f"{BASE_URL}/wp-json/wp/v2/news",
    "graphql": f"{BASE_URL}/graphql",
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

# Directory structure
OUTPUT_DIRECTORIES = ["documents", "metadata", "content", "quarantine", "images", "youtube"]

# Crawler sources
CRAWLER_SOURCES = [
    "wordpress_rest_api",
    "graphql_api",
    "graphql_authenticated",
    "web_scraping",
    "link_discovery",
    "content_extraction",
    "selenium_scraper",
    "youtube_channel",
]

# Rate limiting and timeouts
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_DOWNLOAD_TIMEOUT = 60
DEFAULT_PAGE_DELAY = 0.5
DEFAULT_YOUTUBE_DELAY = 10.0

# Pagination settings
DEFAULT_PER_PAGE = 100
MAX_RETRY_ATTEMPTS = 3

# YouTube configuration
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@nefac"


@dataclass
class CrawlerConfig:
    """Configuration for the NEFAC crawler."""

    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    download_files: bool = True
    # WordPress configuration
    wordpress_base_url: str = BASE_URL
    nefac_base_url: str = BASE_URL  # Add alias for compatibility

    # Authentication
    faust_username: Optional[str] = None
    faust_password: Optional[str] = None
    faust_key: Optional[str] = None  # For backward compatibility

    # Webshare proxy for YouTube
    webshare_username: Optional[str] = None
    webshare_password: Optional[str] = None

    # Rate limiting
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT
    request_delay: float = DEFAULT_PAGE_DELAY
    youtube_delay: float = DEFAULT_YOUTUBE_DELAY
    max_workers: int = 5

    # Retry settings
    max_retries: int = MAX_RETRY_ATTEMPTS

    # Filter settings
    document_types: Optional[Set[str]] = None
    skip_web_scraping: bool = False
    metadata_only: bool = False

    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Ensure output_dir is a Path object
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

        # Create output directories
        for dir_name in OUTPUT_DIRECTORIES:
            dir_path = self.output_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "CrawlerConfig":
        """Load configuration from environment file."""
        env_path = Path(env_file)
        if env_path.exists():
            load_dotenv(env_path)

        return cls(
            output_dir=Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
            download_files=os.getenv("DOWNLOAD_FILES", "true").lower() == "true",
            wordpress_base_url=os.getenv("WORDPRESS_BASE_URL", BASE_URL),
            faust_username=os.getenv("FAUST_USERNAME"),
            faust_password=os.getenv("FAUST_PASSWORD"),
            faust_key=os.getenv("FAUST_SECRET_KEY"),  # Original uses this name
            webshare_username=os.getenv("WEBSHARE_USERNAME"),
            webshare_password=os.getenv("WEBSHARE_PASSWORD"),
            request_delay=float(os.getenv("REQUEST_DELAY", DEFAULT_PAGE_DELAY)),
            youtube_delay=float(os.getenv("YOUTUBE_DELAY", DEFAULT_YOUTUBE_DELAY)),
            max_workers=int(os.getenv("MAX_WORKERS", "5")),
        )

    def validate(self):
        """Validate configuration settings."""
        if not self.wordpress_base_url:
            raise ValueError("WordPress base URL is required")

        if not self.output_dir:
            raise ValueError("Output directory is required")

        if self.max_workers < 1:
            raise ValueError("Max workers must be at least 1")

        if self.request_delay < 0:
            raise ValueError("Request delay cannot be negative")
