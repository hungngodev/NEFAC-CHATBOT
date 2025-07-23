"""
Base extractor class and common functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

from ..core.config import CrawlerConfig
from ..core.types import DocumentInfo, ExtractorResult

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Base class for all content extractors."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.base_url = "https://nefac.org"
        self.discovered_documents = set()

    @abstractmethod
    def extract(self) -> ExtractorResult:
        """Extract documents from the source."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the extraction source."""

    def _create_document_info(self, id_value: str, title: str, source_url: str, mime_type: str, date: str, **kwargs) -> DocumentInfo:
        """Create a standardized DocumentInfo object."""
        return DocumentInfo(id=id_value, title=title, source_url=source_url, mime_type=mime_type, date=date, source=self.source_name, **kwargs)

    def _log_extraction_start(self):
        """Log the start of extraction."""
        logger.info(f"Starting extraction from {self.source_name}...")

    def _log_extraction_result(self, result: ExtractorResult):
        """Log the result of extraction."""
        logger.info(f"Extraction from {self.source_name} completed: {len(result.documents)} documents found")

        if result.errors:
            logger.warning(f"Errors in {self.source_name}: {len(result.errors)}")
            for error in result.errors:
                logger.error(f"  - {error}")

        if result.warnings:
            logger.warning(f"Warnings in {self.source_name}: {len(result.warnings)}")
            for warning in result.warnings:
                logger.warning(f"  - {warning}")


class RequestMixin:
    """Mixin for HTTP request functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session = None

    def get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "NEFAC-Crawler/3.0"})
        return self._session

    def make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with error handling."""
        try:
            session = self.get_session()
            response = session.get(url, timeout=kwargs.get("timeout", self.config.request_timeout), **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None


class PaginationMixin:
    """Mixin for paginated API requests."""

    def fetch_paginated(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
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
                logger.debug(f"Fetched page {page} from {endpoint} ({len(items)} items)")

                # Check if we've reached the end
                if len(items) < per_page:
                    break

                page += 1

                # Rate limiting
                import time

                time.sleep(self.config.request_delay)

            except Exception as e:
                logger.error(f"Error processing page {page} from {endpoint}: {e}")
                break

        return all_items
