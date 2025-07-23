"""
HTML content downloader for NEFAC crawler.
Downloads and processes HTML pages discovered by link scraper.
"""

import json
import logging
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from ..core.config import CrawlerConfig
from ..utils.common import DateUtils, FileUtils, JSONUtils

logger = logging.getLogger(__name__)


class HTMLContentDownloader:
    """Downloads and processes HTML content from discovered links."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.content_dir = config.output_dir / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self._session = None

    def get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "NEFAC-Crawler/3.0"})
        return self._session

    def download_html_pages_from_links(self) -> List[Dict[str, Any]]:
        """Download HTML content from all discovered URLs using link-scraper results."""
        logger.info("Downloading HTML content from discovered links...")

        link_results_path = self.config.output_dir / "link_discovery_results.json"
        html_pages_metadata = []

        if not link_results_path.exists():
            logger.warning("Link discovery results not found, skipping HTML download")
            return html_pages_metadata

        try:
            with open(link_results_path, "r") as f:
                urls_to_scrape = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load link discovery results: {e}")
            return html_pages_metadata

        logger.info(f"Found {len(urls_to_scrape)} URLs to scrape from link discovery results.")

        for url in urls_to_scrape:
            try:
                # Skip document URLs - those are handled by document downloader
                if self._is_document_url(url):
                    continue

                # Download and process HTML content
                html_metadata = self._download_html_page(url)
                if html_metadata:
                    html_pages_metadata.append(html_metadata)

            except Exception as e:
                logger.error(f"Failed to download HTML page {url}: {e}")

        # Save metadata
        if html_pages_metadata:
            html_metadata_file = self.config.output_dir / "metadata" / "html_pages_metadata.json"
            JSONUtils.save_json(html_pages_metadata, html_metadata_file)
            logger.info(f"Saved metadata for {len(html_pages_metadata)} HTML pages.")

        return html_pages_metadata

    def _is_document_url(self, url: str) -> bool:
        """Check if URL points to a document file."""
        from urllib.parse import urlparse

        from ..core.config import DOCUMENT_EXTENSIONS

        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        return any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS)

    def _download_html_page(self, url: str) -> Dict[str, Any]:
        """Download and process a single HTML page."""
        try:
            session = self.get_session()
            response = session.get(url, timeout=30)
            response.raise_for_status()

            # Parse HTML content
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract title
            title = self._extract_title_from_html(str(soup))

            # Generate filename
            clean_title = FileUtils.generate_safe_filename(title)
            filename = f"{clean_title}.html"
            filepath = self.content_dir / filename

            # Ensure unique filename
            counter = 1
            while filepath.exists():
                filename = f"{clean_title}_{counter}.html"
                filepath = self.content_dir / filename
                counter += 1

            # Save HTML content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(response.text)

            # Create metadata
            html_metadata = {
                "title": title,
                "source_url": url,
                "filename": filename,
                "file_path": str(filepath.relative_to(self.config.output_dir)),
                "file_size": filepath.stat().st_size,
                "mime_type": "text/html",
                "download_date": DateUtils.get_current_iso_string(),
                "http_status_code": response.status_code,
                "source": "link_discovery",
                "crawler_version": "3.0",
                "content_length": len(response.text),
                "charset": response.encoding or "utf-8",
            }

            return html_metadata

        except Exception as e:
            logger.error(f"Failed to download HTML page {url}: {e}")
            return None

    def _extract_title_from_html(self, html_content: str) -> str:
        """Extract title from HTML content."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Try to get title tag
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return title_tag.string.strip()

            # Try to get h1 tag
            h1_tag = soup.find("h1")
            if h1_tag and h1_tag.get_text():
                return h1_tag.get_text().strip()

            # Try meta title
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                return meta_title.get("content").strip()

        except Exception:
            pass

        return "Untitled"
