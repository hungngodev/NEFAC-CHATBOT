"""
Link discovery extractor for NEFAC documents.
Integrates with the existing link-scraper tool.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from ..core.types import CrawlerSource, DocumentInfo, ExtractorResult
from ..utils.common import FileUtils
from .base import BaseExtractor

logger = logging.getLogger(__name__)


class LinkDiscoveryExtractor(BaseExtractor):
    """Extractor that uses the link-scraper tool for comprehensive link discovery."""

    @property
    def source_name(self) -> str:
        return CrawlerSource.LINK_DISCOVERY.value

    def extract(self) -> ExtractorResult:
        """Extract documents using link discovery tool."""
        self._log_extraction_start()

        result = ExtractorResult(documents=[])

        try:
            # Run link scraper
            discovered_links = self._run_link_scraper()

            # Convert links to DocumentInfo
            documents = self._process_discovered_links(discovered_links)
            result.documents = documents

            # Also save the raw link discovery results for HTML page downloading
            self._save_link_discovery_results(discovered_links)

        except Exception as e:
            error_msg = f"Error in link discovery: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_extraction_result(result)
        return result

    def _run_link_scraper(self) -> List[str]:
        """Run the existing link-scraper tool to discover document links."""
        logger.info("Running link-scraper tool to discover document links...")

        # Path to link scraper
        link_scraper_path = Path(__file__).parent.parent / "tools" / "link-scraper" / "main.py"

        if not link_scraper_path.exists():
            logger.warning(f"Link scraper not found at {link_scraper_path}")
            return []

        try:
            # Run link scraper with document attachment discovery
            cmd = ["python", str(link_scraper_path), "--base-url", self.config.wordpress_base_url, "--max-depth", "3", "--include-attachments", "--output", str(self.config.output_dir / "link_discovery_raw.json")]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=link_scraper_path.parent,
            )

            if result.returncode != 0:
                logger.error(f"Link scraper failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return []

            # Read the results
            output_file = self.config.output_dir / "link_discovery_raw.json"
            if output_file.exists():
                with open(output_file, "r") as f:
                    data = json.load(f)

                # Extract URLs from the crawl results
                urls = []
                if isinstance(data, dict) and "visited" in data:
                    urls = list(data["visited"].keys())
                elif isinstance(data, list):
                    urls = data

                logger.info(f"Link scraper discovered {len(urls)} URLs")
                return urls
            else:
                logger.warning("Link scraper output file not found")
                return []

        except subprocess.TimeoutExpired:
            logger.error("Link scraper timed out after 10 minutes")
            return []
        except Exception as e:
            logger.error(f"Error running link scraper: {e}")
            return []

    def _process_discovered_links(self, urls: List[str]) -> List[DocumentInfo]:
        """Convert discovered URLs to DocumentInfo objects for document URLs only."""
        documents = []

        for url in urls:
            try:
                # Only process document URLs
                if self._is_document_url(url):
                    doc_info = self._create_document_from_url(url)
                    if doc_info:
                        documents.append(doc_info)
            except Exception as e:
                logger.warning(f"Failed to process URL {url}: {e}")

        logger.info(f"Processed {len(documents)} document URLs from link discovery")
        return documents

    def _is_document_url(self, url: str) -> bool:
        """Check if URL points to a document we want to download."""
        from ..core.config import DOCUMENT_EXTENSIONS

        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        return any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS)

    def _create_document_from_url(self, url: str) -> DocumentInfo:
        """Create DocumentInfo from discovered URL."""
        filename = FileUtils.get_filename_from_url(url)
        title = FileUtils.extract_title_from_url(url)

        return self._create_document_info(id_value=f"link-discovery-{hash(url)}", title=title, source_url=url, mime_type=FileUtils.guess_mime_type(url), date="", filename=filename, description="Discovered via link scraper")  # Will be determined during download

    def _save_link_discovery_results(self, urls: List[str]):
        """Save link discovery results for use by other parts of the crawler."""
        results_file = self.config.output_dir / "link_discovery_results.json"

        try:
            with open(results_file, "w") as f:
                json.dump(urls, f, indent=2)
            logger.info(f"Saved {len(urls)} discovered URLs to {results_file}")
        except Exception as e:
            logger.error(f"Failed to save link discovery results: {e}")
