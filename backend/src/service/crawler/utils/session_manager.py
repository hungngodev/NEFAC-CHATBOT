"""Session Manager for HTTP requests with retry logic and rate limiting."""

import logging
import time
from typing import Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages HTTP sessions with retry logic and rate limiting."""

    _default_session: Optional[requests.Session] = None
    _retry_session: Optional[requests.Session] = None

    @classmethod
    def get_default_session(cls) -> requests.Session:
        """Get or create a default HTTP session with basic configuration."""
        if cls._default_session is None:
            cls._default_session = cls._create_session()
        return cls._default_session

    @classmethod
    def get_retry_session(cls, retry_config: Optional[Dict] = None) -> requests.Session:
        """Get or create a session with advanced retry configuration."""
        if cls._retry_session is None:
            cls._retry_session = cls._create_session(
                with_retry=True, retry_config=retry_config
            )
        return cls._retry_session

    @classmethod
    def _create_session(
        cls, with_retry: bool = False, retry_config: Optional[Dict] = None
    ) -> requests.Session:
        """Create a new HTTP session with optional retry logic."""
        session = requests.Session()

        # Set enhanced headers to avoid blocking
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
        )

        # Disable SSL verification for problematic external sites
        session.verify = False

        # Suppress SSL warnings
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if with_retry:
            # Configure retry strategy
            retry_config = retry_config or {}
            retry_strategy = Retry(
                total=retry_config.get("total", 3),
                status_forcelist=retry_config.get(
                    "status_forcelist", [429, 500, 502, 503, 504]
                ),
                allowed_methods=retry_config.get(
                    "allowed_methods", ["HEAD", "GET", "OPTIONS"]
                ),
                backoff_factor=retry_config.get("backoff_factor", 1),
                raise_on_status=retry_config.get("raise_on_status", False),
            )

            # Mount adapter with retry strategy
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            logger.info(f"Created session with retry strategy: {retry_strategy}")

        return session

    @classmethod
    def close_all_sessions(cls):
        """Close all managed sessions."""
        if cls._default_session:
            cls._default_session.close()
            cls._default_session = None

        if cls._retry_session:
            cls._retry_session.close()
            cls._retry_session = None

        logger.info("All HTTP sessions closed")


def rate_limit(delay: float = 1.0):
    """Simple rate limiting decorator."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            time.sleep(delay)
            return func(*args, **kwargs)

        return wrapper

    return decorator
