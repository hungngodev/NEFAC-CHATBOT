"""
Simplified base extractor for NEFAC crawler.
"""

import logging
from abc import ABC, abstractmethod

import requests

from src.schemas.metadata import BaseMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import ExtractorResult

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Base class for all extractors."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; NEFAC-Crawler/1.0)"})

    @abstractmethod
    def extract(self, **kwargs) -> ExtractorResult:
        """Extract documents from source."""

    def _create_document_info(self, id_value: str, title: str, source_url: str, mime_type: str, date: str = "", filename: str | None = None, **kwargs) -> BaseMetadata:
        """Create a BaseMetadata object."""
        # Generate filename if not provided
        if filename is None:
            filename = self._generate_filename_from_url(source_url, id_value)

        return BaseMetadata(id=id_value, title=title, filename=filename, source_url=source_url, mime_type=mime_type, date=date, source=self.__class__.__name__.replace("Extractor", "").lower(), **kwargs)

    def _generate_filename_from_url(self, source_url: str, id_value: str) -> str:
        """Generate filename from URL or use fallback with ID."""
        if not source_url:
            return f"document_{id_value}"

        # Extract filename from source_url
        filename = source_url.split("/")[-1] or f"document_{id_value}"

        # Remove query parameters if present
        if "?" in filename:
            filename = filename.split("?")[0]

        return filename or f"document_{id_value}"
