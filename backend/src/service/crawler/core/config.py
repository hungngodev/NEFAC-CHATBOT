"""
Simplified configuration for NEFAC crawler.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Constants
BASE_URL = "https://nefac.org"
DEFAULT_OUTPUT_DIR = "nefac_documents"

# File type mappings (simplified)
FILE_TYPES = {".pdf": "pdf", ".doc": "doc", ".docx": "docx", ".xls": "xls", ".xlsx": "xlsx", ".txt": "txt", ".csv": "csv", ".zip": "archives", ".html": "html", ".jpg": "images", ".png": "images", ".gif": "images"}

# Directory mappings for file types
FILE_TYPE_DIRECTORIES = {
    ".pdf": "pdf",
    ".doc": "documents",
    ".docx": "documents",
    ".xls": "xlsx",
    ".xlsx": "xlsx",
    ".csv": "xlsx",
    ".txt": "documents",
    ".html": "html",
    ".htm": "html",
    ".zip": "archives",
    ".rar": "archives",
    ".7z": "archives",
    ".jpg": "images",
    ".jpeg": "images",
    ".png": "images",
    ".gif": "images",
    ".mp4": "videos",
    ".avi": "videos",
    ".mov": "videos",
    ".mp3": "audio",
    ".wav": "audio",
}


@dataclass
class YouTubeConfig:
    """YouTube configuration."""

    enabled: bool = True
    channel_url: str = "https://www.youtube.com/@nefac"
    max_videos: int = 1000
    request_delay: float = 45.0  # Increased base delay
    min_delay: float = 35.0  # Minimum delay between requests
    max_delay: float = 180.0  # Maximum delay for backoff
    backoff_multiplier: float = 1.5  # Progressive backoff multiplier
    api_key: str | None = None
    output_subdir: str = "youtube"
    webshare_username: str | None = None
    webshare_password: str | None = None
    max_retries: int = 3  # Max retries before skipping
    skip_on_error: bool = True  # Skip videos that fail


@dataclass
class CrawlerConfig:
    """Simplified crawler configuration."""

    # Core settings
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    wordpress_base_url: str = BASE_URL
    download_files: bool = True

    # Performance
    max_workers: int = 10
    request_delay: float = 0.1
    request_timeout: int = 60
    max_retries: int = 3
    max_concurrent_requests: int = 10
    batch_size: int = 50

    # Features
    enable_youtube_integration: bool = True
    enable_external_crawling: bool = True

    # YouTube config
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)

    # Auth
    faust_username: str | None = None
    faust_password: str | None = None

    def __post_init__(self):
        """Ensure output directory exists."""
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def set_output_dir(self, path: str | Path) -> None:
        """Set output directory, ensuring it's a Path object."""
        if isinstance(path, str):
            self.output_dir = Path(path)
        else:
            self.output_dir = path
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "CrawlerConfig":
        """Load configuration from environment."""
        if Path(env_file).exists():
            load_dotenv(env_file)

        def get_bool(key: str, default: bool) -> bool:
            return os.getenv(key, str(default)).lower() == "true"

        def get_int(key: str, default: int) -> int:
            return int(os.getenv(key, str(default)))

        def get_float(key: str, default: float) -> float:
            return float(os.getenv(key, str(default)))

        youtube_config = YouTubeConfig(
            enabled=get_bool("YOUTUBE_ENABLED", True),
            channel_url=os.getenv("YOUTUBE_CHANNEL", "https://www.youtube.com/@nefac"),
            max_videos=get_int("YOUTUBE_MAX_VIDEOS", 1000),
            request_delay=get_float("YOUTUBE_DELAY", 45.0),
            min_delay=get_float("YOUTUBE_MIN_DELAY", 35.0),
            max_delay=get_float("YOUTUBE_MAX_DELAY", 180.0),
            backoff_multiplier=get_float("YOUTUBE_BACKOFF_MULTIPLIER", 1.5),
            api_key=os.getenv("YOUTUBE_API_KEY"),
            webshare_username=os.getenv("WEBSHARE_USERNAME"),
            webshare_password=os.getenv("WEBSHARE_PASSWORD"),
            max_retries=get_int("YOUTUBE_MAX_RETRIES", 3),
            skip_on_error=get_bool("YOUTUBE_SKIP_ON_ERROR", True),
        )

        return cls(
            output_dir=Path(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
            wordpress_base_url=os.getenv("WORDPRESS_URL", BASE_URL),
            download_files=get_bool("DOWNLOAD_FILES", True),
            max_workers=get_int("MAX_WORKERS", 10),
            request_delay=get_float("REQUEST_DELAY", 0.1),
            request_timeout=get_int("REQUEST_TIMEOUT", 60),
            max_retries=get_int("MAX_RETRIES", 3),
            max_concurrent_requests=get_int("MAX_CONCURRENT", 10),
            batch_size=get_int("BATCH_SIZE", 50),
            enable_youtube_integration=get_bool("ENABLE_YOUTUBE", True),
            enable_external_crawling=get_bool("ENABLE_EXTERNAL", True),
            youtube=youtube_config,
            faust_username=os.getenv("FAUST_USERNAME"),
            faust_password=os.getenv("FAUST_PASSWORD"),
        )
