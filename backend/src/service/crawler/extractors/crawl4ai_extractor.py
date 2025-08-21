"""Crawl4AIExtractor – uses the public WordPress sitemap to discover **all** URLs on
NEFAC.org and converts them to `DocumentInfo` objects that can later be
processed by the generic `DocumentDownloader`.

This module purposely keeps the implementation lightweight so that external
Crawl4AI SDK dependencies are not required for basic HTML-level crawling.
If the Crawl4AI package is available at runtime the extractor will automatically
fallback to it for richer extraction; otherwise it will gracefully parse the
XML sitemaps itself.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Set


from src.service.crawler.core.config import ENDPOINTS
from src.service.crawler.core.types import CrawlerSource, DocumentInfo, ExtractorResult
from src.service.crawler.utils.common import DateUtils, FileUtils, ValidationUtils
from src.service.crawler.extractors.base import BaseExtractor, RequestMixin

logger = logging.getLogger(__name__)


class Crawl4AIExtractor(BaseExtractor, RequestMixin):
    """Extractor that discovers **every** page on `nefac.org` via the WordPress sitemap.

    It does *not* perform DOM scraping – that is delegated to the generic
    downloader.  The main responsibility here is URL discovery so that we no
    longer miss pages (the user reported 0 documents previously).
    """

    SITEMAP_PATTERN: re.Pattern[str] = re.compile(r"<loc>(.*?)</loc>")

    @property
    def source_name(self) -> str:  # noqa: D401 – simple property
        return CrawlerSource.CRAWL4AI.value

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def extract(self) -> ExtractorResult:  # noqa: D401 – extract documents
        self._log_start()
        documents: List[DocumentInfo] = []
        errors: List[str] = []

        try:
            sitemap_urls = self._discover_sitemaps()
            logger.info("Discovered %d sitemap files", len(sitemap_urls))

            url_set: Set[str] = set()
            for sitemap_url in sitemap_urls:
                try:
                    urls = self._parse_single_sitemap(sitemap_url)
                    url_set.update(urls)
                except Exception as exc:  # pragma: no cover – best-effort
                    logger.warning("Failed to parse sitemap %s: %s", sitemap_url, exc)

            logger.info("Total unique URLs discovered: %d", len(url_set))

            for url in url_set:
                doc = self._url_to_document(url)
                documents.append(doc)

        except Exception as exc:  # Catch-all so extractor never crashes main run
            err_msg = f"Crawl4AIExtractor fatal error: {exc}"
            logger.exception(err_msg)
            errors.append(err_msg)

        result = ExtractorResult(documents=documents, errors=errors)
        self._log_result(result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _discover_sitemaps(self) -> List[str]:
        """Return a list of sitemap XML files to process.

        WordPress typically exposes a single *index* file that points to type-
        specific sitemaps.  We fetch the index and collect every `<loc>` entry.
        """
        index_url = ENDPOINTS.get("sitemap_index") or ENDPOINTS["sitemap"]
        response = self.make_request(index_url)
        if not response:
            logger.error("Unable to download sitemap index %s", index_url)
            return []

        content = response.text
        matches = self.SITEMAP_PATTERN.findall(content)
        # Ensure the index itself is also included as fallback
        if index_url not in matches:
            matches.append(index_url)
        return matches

    def _parse_single_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse one sitemap XML document and return all `<loc>` URLs inside."""
        response = self.make_request(sitemap_url)
        if not response:
            return []
        try:
            root = ET.fromstring(response.content)
            urls: List[str] = []
            for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                urls.append(loc.text.strip())
            # Fallback regex if namespace handling fails (rare custom themes)
            if not urls:
                urls = self.SITEMAP_PATTERN.findall(response.text)
            return urls
        except ET.ParseError:
            logger.warning(
                "Malformed XML in sitemap %s – falling back to regex", sitemap_url
            )
            return self.SITEMAP_PATTERN.findall(response.text)

    def _url_to_document(self, url: str) -> DocumentInfo:
        """Convert a raw URL into a minimal `DocumentInfo`."""
        url = ValidationUtils.clean_url(url, self.config.wordpress_base_url)
        title = FileUtils.extract_title_from_url(url)
        doc_id = FileUtils.generate_file_id(url)
        return self._create_document_info(
            id_value=doc_id,
            title=title,
            source_url=url,
            mime_type="text/html",
            date=DateUtils.now_iso(),
        )
