"""
Base Extractor Classes and Common Functionality

┌─────────────────────────────────────────────────────────────────────────────┐
│                        Extractor Hierarchy                              │
│                                                                         │
│  ┌─────────────────┐                                                    │
│  │  BaseExtractor  │                                                    │
│  │  (Abstract)     │                                                    │
│  └─────────────────┘                                                    │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐      │
│  │  RequestMixin   │    │ PaginationMixin │    │ URLCleanerMixin │      │
│  │  (HTTP Helper)  │    │ (API Paging)    │    │ (URL Handling)  │      │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘      │
│          │                                                               │
│          ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    Concrete Extractors                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐   │ │
│  │  │ WordPress   │  │ GraphQL     │  │ Crawl4AI (Unified)       │   │ │
│  │  │ Extractor   │  │ Extractor   │  │ Extractor                │   │ │
│  │  └─────────────┘  └─────────────┘  └──────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

This module provides the foundation for all content extractors in the NEFAC crawler.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import List, Optional
from urllib.parse import urljoin

import requests

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import DocumentInfo, ExtractorResult
from src.service.crawler.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Abstract Base Class for All Content Extractors"""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.base_url = "https://nefac.org"
        self._session = None
        self.discovered_documents = set()

    @abstractmethod
    def extract(self, *args, **kwargs) -> ExtractorResult:
        """Extract documents from the source."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the extraction source."""

    def _create_document_info(
        self,
        id_value: str,
        title: str,
        source_url: str,
        mime_type: str,
        date: str,
        **kwargs,
    ) -> DocumentInfo:
        """Create a standardized DocumentInfo object."""
        return DocumentInfo(
            id=id_value,
            title=title,
            source_url=source_url,
            mime_type=mime_type,
            date=date,
            source=self.source_name,
            **kwargs,
        )

    def _log_start(self):
        """Log the start of extraction process."""
        logger.info(f"Starting extraction from {self.source_name}")

    def _log_result(self, result: ExtractorResult):
        """Log the result of extraction process."""
        logger.info(
            f"Completed extraction from {self.source_name}: {len(result.documents)} documents"
        )
        if result.warnings:
            logger.warning(f"Warnings from {self.source_name}: {len(result.warnings)}")
        if result.errors:
            logger.error(f"Errors from {self.source_name}: {len(result.errors)}")

    def _safe_process_items(self, items, processor_func, item_type="items"):
        """Safely process a list of items with error handling."""
        results = []
        for item in items:
            try:
                processed = processor_func(item)
                if processed:
                    (
                        results.extend(processed)
                        if isinstance(processed, list)
                        else results.append(processed)
                    )
            except Exception as e:
                logger.warning(f"Error processing {item_type}: {e}")
        return results

    def _clean_url(self, raw_url: str, base_url: str = None) -> str:
        """Clean and normalize URLs."""
        if not raw_url:
            return ""

        # Use provided base_url or default to config.wordpress_base_url
        base = base_url or getattr(self.config, "wordpress_base_url", "")

        if raw_url.startswith("/"):
            return urljoin(base, raw_url)
        elif raw_url.startswith("http"):
            return raw_url
        else:
            return urljoin(base, raw_url)


class RequestMixin:
    """Mixin for HTTP request functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session = None

    @property
    def session(self):
        """Get or create HTTP session with default headers."""
        if self._session is None:
            self._session = SessionManager.get_default_session()
        return self._session

    def make_request(self, url: str, **kwargs):
        """Make HTTP request with error handling."""
        try:
            response = self.session.get(
                url, timeout=self.config.request_timeout, **kwargs
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None


class PaginationMixin:
    """Mixin for paginated API requests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def fetch_paginated(
        self, endpoint: str, params: Optional[dict] = None
    ) -> List[dict]:
        """Fetch all items from a paginated endpoint."""
        if params is None:
            params = {}

        all_items = []
        page = 1
        per_page = 100

        while True:
            page_params = params.copy()
            page_params.update({"page": page, "per_page": per_page, "_embed": "true"})

            response = self.make_request(endpoint, params=page_params)
            if not response:
                break

            try:
                items = response.json()
                if not items:
                    break

                all_items.extend(items)
                logger.debug(
                    f"Fetched page {page} from {endpoint} ({len(items)} items)"
                )

                # Check if we've reached the end
                if len(items) < per_page:
                    break

                page += 1

                # Rate limiting
                time.sleep(self.config.request_delay)

            except Exception as e:
                logger.error(f"Error processing page {page} from {endpoint}: {e}")
                break

        return all_items
