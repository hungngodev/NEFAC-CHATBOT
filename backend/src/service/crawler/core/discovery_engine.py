"""
Enhanced discovery engine for NEFAC crawler.
Handles URL discovery, categorization, and filtering.
Consolidates functionality from both DiscoveryEngine and SitemapParser.
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import ContentType, SitemapEntry, URLEntry
from src.service.crawler.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """Discover and categorize URLs for processing."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.base_url = "https://nefac.org"
        self.sitemap_url = "https://nefac.org/wp-sitemap.xml"
        self._session = None

        # WordPress sitemap namespaces
        self.namespaces = {
            "sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9",
            "image": "http://www.google.com/schemas/sitemap-image/1.1",
            "news": "http://www.google.com/schemas/sitemap-news/0.9",
        }

        # URL patterns for different content types
        self.document_patterns = [
            r"\.pdf$",
            r"\.doc$",
            r"\.docx$",
            r"\.xls$",
            r"\.xlsx$",
            r"\.ppt$",
            r"\.pptx$",
            r"\.csv$",
            r"\.txt$",
            r"\.rtf$",
        ]

        self.image_patterns = [
            r"\.jpg$",
            r"\.jpeg$",
            r"\.png$",
            r"\.gif$",
            r"\.bmp$",
            r"\.svg$",
            r"\.tiff$",
            r"\.webp$",
        ]

        self.archive_patterns = [r"\.zip$", r"\.rar$", r"\.7z$", r"\.tar$", r"\.gz$"]

        # External domain whitelist (configurable)
        self.external_whitelist = getattr(
            config,
            "external_domain_whitelist",
            [
                "youtube.com",
                "youtu.be",
                "vimeo.com",
                "docs.google.com",
                "drive.google.com",
                "scribd.com",
                "issuu.com",
                "supremecourt.gov",
                "courts.state.nh.us",
                "mass.gov",
                "ct.gov",
                "vermont.gov",
                "maine.gov",
                "ri.gov",
            ],
        )

    @property
    def session(self) -> requests.Session:
        """Get or create HTTP session with retry strategy."""
        if self._session is None:
            # Configure retry strategy
            retry_config = {
                "total": 3,
                "status_forcelist": [429, 500, 502, 503, 504],
                "backoff_factor": 1,
                "raise_on_status": False,
            }
            self._session = SessionManager.get_retry_session(retry_config)

            # Set additional headers
            self._session.headers.update(
                {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                }
            )
        return self._session

    def parse_sitemap_index(self, url: Optional[str] = None) -> List[str]:
        """Parse sitemap index and return list of sitemap URLs."""
        if url is None:
            url = self.sitemap_url

        logger.info(f"Parsing sitemap index: {url}")

        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            sitemap_urls = []

            # Handle sitemap index format
            if root.tag.endswith("sitemapindex"):
                for sitemap in root.findall(".//sitemap:sitemap", self.namespaces):
                    loc_elem = sitemap.find("sitemap:loc", self.namespaces)
                    if loc_elem is not None and loc_elem.text:
                        sitemap_urls.append(loc_elem.text.strip())

            # Handle single sitemap format
            elif root.tag.endswith("urlset"):
                sitemap_urls.append(url)

            logger.info(f"Found {len(sitemap_urls)} sitemap(s)")
            return sitemap_urls

        except requests.RequestException as e:
            logger.error(f"Failed to fetch sitemap index {url}: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap index XML {url}: {e}")
            return []

    def parse_sitemap(self, url: str) -> List[SitemapEntry]:
        """Parse individual sitemap and extract URL entries."""
        logger.info(f"Parsing sitemap: {url}")

        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            entries = []

            # Parse URL entries
            for url_elem in root.findall(".//sitemap:url", self.namespaces):
                entry = self._parse_url_element(url_elem, url)
                if entry:
                    entries.append(entry)

            logger.info(f"Extracted {len(entries)} URLs from {url}")
            return entries

        except requests.RequestException as e:
            logger.error(f"Failed to fetch sitemap {url}: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap XML {url}: {e}")
            return []

    def _parse_url_element(
        self, url_elem: ET.Element, sitemap_source: str
    ) -> Optional[SitemapEntry]:
        """Parse individual URL element from sitemap."""
        try:
            # Extract URL
            loc_elem = url_elem.find("sitemap:loc", self.namespaces)
            if loc_elem is None or not loc_elem.text:
                return None

            url = loc_elem.text.strip()

            # Extract lastmod
            lastmod = None
            lastmod_elem = url_elem.find("sitemap:lastmod", self.namespaces)
            if lastmod_elem is not None and lastmod_elem.text:
                try:
                    # Parse ISO format datetime
                    lastmod_str = lastmod_elem.text.strip()
                    # Handle different datetime formats
                    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                        try:
                            lastmod = datetime.strptime(
                                lastmod_str.replace("Z", "+00:00"), fmt
                            )
                            break
                        except ValueError:
                            continue
                except ValueError as e:
                    logger.warning(
                        f"Failed to parse lastmod '{lastmod_elem.text}': {e}"
                    )

            # Extract changefreq
            changefreq = None
            changefreq_elem = url_elem.find("sitemap:changefreq", self.namespaces)
            if changefreq_elem is not None and changefreq_elem.text:
                changefreq = changefreq_elem.text.strip()

            # Extract priority
            priority = None
            priority_elem = url_elem.find("sitemap:priority", self.namespaces)
            if priority_elem is not None and priority_elem.text:
                try:
                    priority = float(priority_elem.text.strip())
                except ValueError:
                    pass

            return SitemapEntry(
                url=url,
                lastmod=lastmod,
                changefreq=changefreq,
                priority=priority,
                sitemap_source=sitemap_source,
            )

        except Exception as e:
            logger.error(f"Error parsing URL element: {e}")
            return None

    def get_all_urls(
        self, since: Optional[datetime] = None, max_urls: Optional[int] = None
    ) -> List[URLEntry]:
        """Get all URLs from all sitemaps, optionally filtered by date with comprehensive error handling."""
        logger.info("Starting comprehensive sitemap crawl of NEFAC website")

        # Parse sitemap index
        sitemap_urls = self.parse_sitemap_index()

        if not sitemap_urls:
            logger.warning(
                "No sitemaps found in sitemap index, trying direct sitemap access"
            )
            sitemap_urls = [self.sitemap_url]

        all_entries = []
        failed_sitemaps = []

        # Parse each sitemap with better error handling
        for sitemap_url in sitemap_urls:
            try:
                logger.info(f"Processing sitemap: {sitemap_url}")
                entries = self.parse_sitemap(sitemap_url)

                # Filter by date if specified
                if since:
                    entries = [e for e in entries if e.lastmod and e.lastmod >= since]

                all_entries.extend(entries)
                logger.info(f"Added {len(entries)} URLs from {sitemap_url}")

            except Exception as e:
                logger.error(f"Failed to process sitemap {sitemap_url}: {e}")
                failed_sitemaps.append(sitemap_url)
                continue

        # Sort by priority (most important first)
        all_entries.sort(key=lambda x: self._calculate_priority(x), reverse=True)

        # Apply max_urls limit if specified
        if max_urls and len(all_entries) > max_urls:
            logger.info(
                f"Limiting URLs from {len(all_entries)} to {max_urls} (highest priority)"
            )
            all_entries = all_entries[:max_urls]

        # Convert to URLEntry objects
        url_entries = []
        for entry in all_entries:
            url_entry = URLEntry(
                url=entry.url,
                source="sitemap",
                priority=self._calculate_priority(entry),
                content_type_hint=self._guess_content_type(entry.url),
            )
            url_entries.append(url_entry)

        logger.info(f"Total URLs discovered and prioritized: {len(url_entries)}")

        # Log failed sitemaps
        if failed_sitemaps:
            logger.warning(f"Failed to process {len(failed_sitemaps)} sitemaps:")
            for sitemap_url in failed_sitemaps[:10]:  # Limit to first 10
                logger.warning(f"  - {sitemap_url}")
            if len(failed_sitemaps) > 10:
                logger.warning(f"  ... and {len(failed_sitemaps) - 10} more")

        # Log URL breakdown for debugging
        self._log_url_breakdown(url_entries)

        # Save sitemap processing report
        self._save_sitemap_report(url_entries, failed_sitemaps)

        return url_entries

    def _log_url_breakdown(self, url_entries: List[URLEntry]) -> None:
        """Log breakdown of discovered URLs by type."""
        type_counts = {}
        for entry in url_entries:
            content_type = entry.content_type_hint or "unknown"
            type_counts[content_type] = type_counts.get(content_type, 0) + 1

        logger.info("URL breakdown by content type:")
        for content_type, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"  {content_type}: {count} URLs")

        # Show sample URLs for each type
        if logger.isEnabledFor(logging.DEBUG):
            for content_type in type_counts:
                sample_urls = [
                    e.url for e in url_entries if e.content_type_hint == content_type
                ][:3]
                logger.debug(f"  Sample {content_type} URLs: {sample_urls}")

    def _save_sitemap_report(
        self, url_entries: List[URLEntry], failed_sitemaps: List[str]
    ) -> None:
        """Save a comprehensive sitemap processing report."""
        try:
            report_file = self.config.output_dir / "sitemap_processing_report.txt"

            with open(report_file, "w") as f:
                f.write("NEFAC Crawler Sitemap Processing Report\n")
                f.write("=====================================\n\n")

                f.write(f"Total URLs Discovered: {len(url_entries)}\n\n")

                # Content type breakdown
                type_counts = {}
                for entry in url_entries:
                    content_type = entry.content_type_hint or "unknown"
                    type_counts[content_type] = type_counts.get(content_type, 0) + 1

                f.write("Content Type Breakdown:\n")
                for content_type, count in sorted(
                    type_counts.items(), key=lambda x: x[1], reverse=True
                ):
                    f.write(f"  {content_type}: {count} URLs\n")
                f.write("\n")

                # Failed sitemaps
                if failed_sitemaps:
                    f.write(f"Failed Sitemaps ({len(failed_sitemaps)}):\n")
                    for sitemap_url in failed_sitemaps:
                        f.write(f"  - {sitemap_url}\n")
                    f.write("\n")

                f.write(f"Report generated: {datetime.now().isoformat()}\n")

            logger.info(f"Sitemap processing report saved to: {report_file}")
        except Exception as e:
            logger.error(f"Failed to save sitemap processing report: {e}")

    def _log_comprehensive_breakdown(self, url_entries: List[URLEntry]) -> None:
        """Log comprehensive breakdown of ALL discovered URLs."""
        # Count by content type
        type_counts = {}
        source_counts = {}
        file_type_counts = {}

        for entry in url_entries:
            # Content type breakdown
            content_type = entry.content_type_hint or "unknown"
            type_counts[content_type] = type_counts.get(content_type, 0) + 1

            # Source breakdown
            source = entry.source or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1

            # File type breakdown (for documents)
            if hasattr(entry, "url") and entry.url:
                url_lower = entry.url.lower()
                if "." in url_lower:
                    ext = "." + url_lower.split(".")[-1]
                    if ext in [
                        ".pdf",
                        ".doc",
                        ".docx",
                        ".xls",
                        ".xlsx",
                        ".ppt",
                        ".pptx",
                        ".csv",
                        ".txt",
                        ".zip",
                    ]:
                        file_type_counts[ext] = file_type_counts.get(ext, 0) + 1

        logger.info("🎯 COMPREHENSIVE URL DISCOVERY BREAKDOWN:")
        logger.info("=" * 50)

        logger.info("📊 Content Type Breakdown:")
        for content_type, count in sorted(
            type_counts.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"   {content_type}: {count:,} URLs")

        logger.info("\n📡 Source Breakdown:")
        for source, count in sorted(
            source_counts.items(), key=lambda x: x[1], reverse=True
        ):
            logger.info(f"   {source}: {count:,} URLs")

        if file_type_counts:
            logger.info("\n📄 File Type Breakdown:")
            for file_type, count in sorted(
                file_type_counts.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"   {file_type.upper()}: {count:,} files")

        # Priority breakdown
        priority_counts = {}
        for entry in url_entries:
            priority = entry.priority or 0
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        logger.info("\n⭐ Priority Breakdown:")
        for priority, count in sorted(priority_counts.items(), reverse=True):
            logger.info(f"   Priority {priority}: {count:,} URLs")

        logger.info("=" * 50)

    def get_comprehensive_url_discovery(self) -> List[URLEntry]:
        """
        Get comprehensive URL discovery including ALL files and content.
        This method ensures EVERY document, page, and file is discovered.
        """
        logger.info("🌍 Starting COMPREHENSIVE URL discovery - finding EVERYTHING")

        all_urls = []

        # 1. Get ALL URLs from sitemap tree (no limits, all sub-sitemaps)
        logger.info("📋 Phase 1: Complete sitemap discovery")
        sitemap_urls = self._discover_complete_sitemap_tree()
        all_urls.extend(sitemap_urls)
        logger.info(f"✅ Sitemap tree discovery: {len(sitemap_urls)} URLs")

        # 2. Extract ALL file links from discovered pages
        logger.info("📄 Phase 2: File discovery from all pages")
        file_urls = self._discover_all_files_from_pages(sitemap_urls)
        all_urls.extend(file_urls)
        logger.info(f"✅ File discovery: {len(file_urls)} files found")

        # 3. Discover additional URLs through link crawling
        logger.info("🔗 Phase 3: Additional link discovery")
        additional_urls = self._discover_additional_urls()
        all_urls.extend(additional_urls)
        logger.info(f"✅ Additional link discovery: {len(additional_urls)} URLs found")

        # Remove duplicates while preserving order
        seen_urls = set()
        unique_urls = []
        duplicate_count = 0

        for url_entry in all_urls:
            if url_entry.url not in seen_urls:
                seen_urls.add(url_entry.url)
                unique_urls.append(url_entry)
            else:
                duplicate_count += 1

        logger.info(
            f"🎯 Total discovery complete: {len(unique_urls)} unique URLs ({duplicate_count} duplicates removed)"
        )

        # Log comprehensive breakdown
        self._log_comprehensive_breakdown(unique_urls)

        return unique_urls

    def _discover_complete_sitemap_tree(self) -> List[URLEntry]:
        """
        Discover the complete sitemap tree, ensuring ALL sub-sitemaps are crawled.
        The WordPress sitemap is a tree structure with multiple levels.
        """
        all_sitemap_urls = []

        # Start with the main sitemap index
        sitemap_indexes = self.parse_sitemap_index(self.sitemap_url)
        logger.info(f"Found {len(sitemap_indexes)} sitemap indexes")

        # Process each sitemap index (could be nested)
        processed_sitemaps = set()
        to_process = sitemap_indexes.copy()

        while to_process:
            current_sitemap = to_process.pop()

            if current_sitemap in processed_sitemaps:
                continue

            processed_sitemaps.add(current_sitemap)

            # Check if this is another sitemap index or actual sitemap
            try:
                response = self.session.get(
                    current_sitemap, timeout=self.config.request_timeout
                )
                if response.status_code == 200:
                    root = ET.fromstring(response.content)

                    # If it's another sitemap index, add sub-sitemaps to process
                    if root.tag.endswith("sitemapindex"):
                        for sitemap in root.findall(
                            ".//sitemap:sitemap", self.namespaces
                        ):
                            loc_elem = sitemap.find("sitemap:loc", self.namespaces)
                            if loc_elem is not None and loc_elem.text:
                                sub_sitemap = loc_elem.text.strip()
                                if sub_sitemap not in processed_sitemaps:
                                    to_process.append(sub_sitemap)

                    # If it's an actual sitemap, parse all URLs
                    elif root.tag.endswith("urlset"):
                        entries = self.parse_sitemap(current_sitemap)
                        # Convert SitemapEntry objects to URLEntry objects
                        for entry in entries:
                            url_entry = URLEntry(
                                url=entry.url,
                                source="sitemap",
                                priority=self._calculate_priority(entry),
                                content_type_hint=self._guess_content_type(entry.url),
                            )
                            all_sitemap_urls.append(url_entry)
                        logger.info(
                            f"Parsed {len(entries)} URLs from {current_sitemap}"
                        )

            except Exception as e:
                logger.warning(f"Could not process sitemap {current_sitemap}: {e}")

        logger.info(f"Complete sitemap tree parsed: {len(all_sitemap_urls)} total URLs")
        return all_sitemap_urls

    def _discover_all_files_from_pages(
        self, page_urls: List[URLEntry]
    ) -> List[URLEntry]:
        """
        Scan ALL discovered pages to find downloadable files.
        This ensures we get every PDF, Excel, Word document, etc.
        """
        file_urls = []
        file_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".txt",
            ".rtf",
            ".odt",
            ".ods",
            ".odp",
            ".csv",
            ".zip",
            ".json",
            ".xml",
            ".rss",
            ".atom",
            ".epub",
            ".mobi",
        }

        # Skip image files as requested
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".svg",
            ".bmp",
            ".ico",
        }

        # Process in smaller batches to avoid overwhelming server
        batch_size = 5  # Conservative batch size
        total_pages = len(page_urls)

        logger.info(f"Scanning {total_pages} pages for downloadable files...")

        for i in range(0, total_pages, batch_size):
            batch = page_urls[i : i + batch_size]

            for url_entry in batch:
                try:
                    url = url_entry.url

                    # Skip URLs that already look like files
                    url_lower = url.lower()
                    if any(url_lower.endswith(ext) for ext in file_extensions):
                        # It's already a file - just verify it's not an image
                        if not any(
                            url_lower.endswith(img_ext) for img_ext in image_extensions
                        ):
                            file_entry = URLEntry(
                                url=url,
                                content_type_hint=self._detect_content_type(url),
                                priority=5,  # High priority for direct files
                                source="direct_file",
                            )
                            file_urls.append(file_entry)
                        continue

                    # Request the page to scan for file links
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, "html.parser")

                        # Find all links that point to files
                        for link in soup.find_all("a", href=True):
                            href = link["href"]

                            # Convert relative URLs to absolute
                            if href.startswith("/"):
                                file_url = f"https://nefac.org{href}"
                            elif not href.startswith("http"):
                                file_url = f"https://nefac.org/{href.lstrip('/')}"
                            else:
                                file_url = href

                            # Check if it's a file we want (and not an image)
                            file_url_lower = file_url.lower()
                            if any(
                                file_url_lower.endswith(ext) for ext in file_extensions
                            ) and not any(
                                file_url_lower.endswith(img_ext)
                                for img_ext in image_extensions
                            ):

                                file_entry = URLEntry(
                                    url=file_url,
                                    content_type_hint=self._detect_content_type(
                                        file_url
                                    ),
                                    priority=5,  # High priority for documents
                                    source=f"extracted_from:{url_entry.url}",
                                )
                                file_urls.append(file_entry)

                    # Respectful delay
                    time.sleep(0.2)

                except Exception as e:
                    logger.warning(f"Could not scan {url_entry.url} for files: {e}")
                    continue

            # Progress update
            processed = min(i + batch_size, total_pages)
            unique_files = len(set(f.url for f in file_urls))
            logger.info(
                f"📄 Scanned {processed}/{total_pages} pages, found {unique_files} unique files"
            )

        # Remove duplicates while preserving order
        seen_file_urls = set()
        unique_file_urls = []
        for file_entry in file_urls:
            if file_entry.url not in seen_file_urls:
                seen_file_urls.add(file_entry.url)
                unique_file_urls.append(file_entry)

        logger.info(
            f"📄 File discovery complete: {len(unique_file_urls)} unique downloadable files"
        )
        return unique_file_urls

    def _discover_wordpress_api_content(self) -> List[URLEntry]:
        """
        Use WordPress REST API to discover any content not in sitemap.
        """
        api_urls = []

        # WordPress REST API endpoints
        api_endpoints = [
            f"{self.base_url}/wp-json/wp/v2/posts?per_page=100",
            f"{self.base_url}/wp-json/wp/v2/pages?per_page=100",
            f"{self.base_url}/wp-json/wp/v2/media?per_page=100",
            f"{self.base_url}/wp-json/wp/v2/categories?per_page=100",
            f"{self.base_url}/wp-json/wp/v2/tags?per_page=100",
        ]

        for endpoint in api_endpoints:
            try:
                response = self.session.get(
                    endpoint, timeout=self.config.request_timeout
                )
                if response.status_code == 200:
                    data = response.json()

                    for item in data:
                        if "link" in item:
                            url_entry = URLEntry(
                                url=item["link"],
                                content_type_hint=self._guess_content_type(
                                    item["link"]
                                ),
                                priority=3,
                                source="wordpress_api",
                            )
                            api_urls.append(url_entry)

                        # For media items, also get the source URL
                        if "source_url" in item:
                            media_url = item["source_url"]
                            # Only include non-image files
                            if not any(
                                media_url.lower().endswith(ext)
                                for ext in [
                                    ".jpg",
                                    ".jpeg",
                                    ".png",
                                    ".gif",
                                    ".webp",
                                    ".svg",
                                ]
                            ):
                                media_entry = URLEntry(
                                    url=media_url,
                                    content_type_hint=self._detect_content_type(
                                        media_url
                                    ),
                                    priority=4,
                                    source="wordpress_media_api",
                                    title=(
                                        item.get("title", {}).get("rendered", "")[:100]
                                        if "title" in item
                                        else None
                                    ),
                                )
                                api_urls.append(media_entry)

            except Exception as e:
                logger.warning(
                    f"Could not fetch WordPress API endpoint {endpoint}: {e}"
                )

        logger.info(f"WordPress API discovered {len(api_urls)} additional URLs")
        return api_urls

    def _discover_additional_urls(self) -> List[URLEntry]:
        """Discover additional URLs through various means."""
        additional_urls = []

        # Key pages to crawl for more links
        key_pages = [
            f"{self.base_url}/",
            f"{self.base_url}/news/",
            f"{self.base_url}/about/",
            f"{self.base_url}/contact/",
            f"{self.base_url}/resources/",
            f"{self.base_url}/documents/",
        ]

        for page_url in key_pages:
            try:
                response = self.session.get(
                    page_url, timeout=self.config.request_timeout
                )
                if response.status_code == 200:
                    urls = self._extract_links_from_html(response.text, page_url)
                    additional_urls.extend(urls)
                    logger.debug(f"Found {len(urls)} additional URLs from {page_url}")
            except Exception as e:
                logger.warning(f"Could not crawl {page_url} for additional URLs: {e}")

        return additional_urls

    def _extract_links_from_html(
        self, html_content: str, base_url: str
    ) -> List[URLEntry]:
        """Extract document and page links from HTML content."""
        from bs4 import BeautifulSoup

        urls = []
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Find all links
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("/"):
                    full_url = urljoin(self.base_url, href)
                elif href.startswith("http"):
                    # Only include if it's from the same domain or whitelisted
                    parsed = urlparse(href)
                    if parsed.netloc == "nefac.org" or any(
                        domain in parsed.netloc for domain in self.external_whitelist
                    ):
                        full_url = href
                    else:
                        continue
                else:
                    full_url = urljoin(base_url, href)

                # Create URL entry
                url_entry = URLEntry(
                    url=full_url,
                    source="link_discovery",
                    priority=self._calculate_priority_from_url(full_url),
                    content_type_hint=self._guess_content_type(full_url),
                )
                urls.append(url_entry)

        except Exception as e:
            logger.error(f"Error extracting links from HTML: {e}")

        return urls

    def _calculate_priority_from_url(self, url: str) -> int:
        """Calculate priority for a URL without sitemap metadata."""
        priority = 50  # Base priority

        url_lower = url.lower()

        # High priority for documents
        if any(ext in url_lower for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]):
            priority += 100

        # High priority for main content
        if any(pattern in url_lower for pattern in ["/news/", "/posts/", "/articles/"]):
            priority += 75

        # Medium priority for pages
        if any(
            pattern in url_lower for pattern in ["/about/", "/contact/", "/resources/"]
        ):
            priority += 50

        # Lower priority for archives, tags, etc.
        if any(
            pattern in url_lower
            for pattern in ["/tag/", "/category/", "/archive/", "/author/"]
        ):
            priority -= 25

        return max(0, priority)

    def _get_manual_important_urls(self) -> List[URLEntry]:
        """Get manually specified important URLs that might be missed."""
        important_urls = [
            # YouTube channel
            "https://www.youtube.com/@nefac",
            "https://www.youtube.com/channel/UCxxxxxxx",  # Replace with actual channel ID if known
            # Important document directories that might not be in sitemap
            f"{self.base_url}/wp-content/uploads/",
            # RSS feeds and other data sources
            f"{self.base_url}/feed/",
            f"{self.base_url}/news/feed/",
        ]

        url_entries = []
        for url in important_urls:
            url_entry = URLEntry(
                url=url,
                source="manual",
                priority=200,  # High priority for manually specified URLs
                content_type_hint=self._guess_content_type(url),
            )
            url_entries.append(url_entry)

        return url_entries

    def _calculate_priority(self, entry: SitemapEntry) -> int:
        """Calculate priority score for URL entry."""
        priority = 0

        # Base priority from sitemap
        if entry.priority:
            priority += int(entry.priority * 100)

        # Boost based on URL patterns
        url_lower = entry.url.lower()

        # High priority for main content
        if any(pattern in url_lower for pattern in ["/news/", "/posts/", "/articles/"]):
            priority += 50

        # Medium priority for pages
        if any(pattern in url_lower for pattern in ["/page/", "/about/", "/contact/"]):
            priority += 25

        # Low priority for archives, tags, etc.
        if any(
            pattern in url_lower for pattern in ["/tag/", "/category/", "/archive/"]
        ):
            priority -= 25

        # Boost recent content
        if entry.lastmod:
            days_old = (datetime.now() - entry.lastmod.replace(tzinfo=None)).days
            if days_old < 30:
                priority += 30
            elif days_old < 90:
                priority += 15
            elif days_old < 365:
                priority += 5

        return max(0, priority)

    def _guess_content_type(self, url: str) -> Optional[str]:
        """Guess content type from URL patterns."""
        url_lower = url.lower()

        # Document extensions
        if any(
            ext in url_lower
            for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]
        ):
            return "document"

        # Image extensions
        if any(
            ext in url_lower
            for ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"]
        ):
            return "image"

        # Archive extensions
        if any(ext in url_lower for ext in [".zip", ".rar", ".tar", ".gz"]):
            return "archive"

        # YouTube
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube_video"

        # Default to web page
        return "web_page"

    def filter_by_lastmod(
        self, entries: List[SitemapEntry], since: datetime
    ) -> List[SitemapEntry]:
        """Filter sitemap entries by last modification date."""
        filtered = []
        for entry in entries:
            if entry.lastmod and entry.lastmod >= since:
                filtered.append(entry)
            elif not entry.lastmod:
                # Include entries without lastmod (assume they might be new)
                filtered.append(entry)

        logger.info(f"Filtered {len(entries)} entries to {len(filtered)} since {since}")
        return filtered

    def process_sitemap_entries(self, sitemap_entries: List[str]) -> List[URLEntry]:
        """Process sitemap entries and convert to URLEntry format."""
        all_entries = []

        # Parse each sitemap
        for sitemap_url in sitemap_entries:
            entries = self.parse_sitemap(sitemap_url)
            all_entries.extend(entries)

        # Convert to URLEntry objects
        url_entries = []
        for entry in all_entries:
            url_entry = URLEntry(
                url=entry.url,
                source="sitemap",
                priority=self._calculate_priority(entry),
                content_type_hint=self._guess_content_type(entry.url),
            )
            url_entries.append(url_entry)

        return url_entries

    def get_sitemap_stats(self) -> dict:
        """Get statistics about the sitemap structure."""
        sitemap_urls = self.parse_sitemap_index()

        stats = {
            "total_sitemaps": len(sitemap_urls),
            "sitemap_breakdown": {},
            "total_urls": 0,
            "content_types": {},
            "date_range": {"earliest": None, "latest": None},
        }

        for sitemap_url in sitemap_urls:
            entries = self.parse_sitemap(sitemap_url)
            sitemap_name = sitemap_url.split("/")[-1]

            stats["sitemap_breakdown"][sitemap_name] = len(entries)
            stats["total_urls"] += len(entries)

            # Analyze content types and dates
            for entry in entries:
                content_type = self._guess_content_type(entry.url)
                stats["content_types"][content_type] = (
                    stats["content_types"].get(content_type, 0) + 1
                )

                if entry.lastmod:
                    if (
                        not stats["date_range"]["earliest"]
                        or entry.lastmod < stats["date_range"]["earliest"]
                    ):
                        stats["date_range"]["earliest"] = entry.lastmod
                    if (
                        not stats["date_range"]["latest"]
                        or entry.lastmod > stats["date_range"]["latest"]
                    ):
                        stats["date_range"]["latest"] = entry.lastmod

        return stats

    def discover_from_sitemap(self, since: datetime = None) -> List[URLEntry]:
        """Discover URLs from NEFAC sitemap."""
        logger.info("Starting sitemap-based discovery")

        # Get URLs from sitemap
        url_entries = self.get_all_urls(since=since)

        logger.info(f"Discovered {len(url_entries)} URLs from sitemap")
        return url_entries

    def discover_external_links(self, url: str, max_depth: int = 1) -> List[URLEntry]:
        """Discover external links from a given URL."""
        logger.info(f"Discovering external links from: {url}")

        try:
            response = self.session.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            external_urls = set()

            # Find all links
            for link in soup.find_all("a", href=True):
                href = link["href"]

                # Convert relative URLs to absolute
                absolute_url = urljoin(url, href)

                # Check if external and whitelisted
                if self._is_external_url(absolute_url) and self.should_crawl_external(
                    absolute_url
                ):
                    external_urls.add(absolute_url)

            # Convert to URLEntry objects
            url_entries = []
            for ext_url in external_urls:
                entry = URLEntry(
                    url=ext_url,
                    source="external_link",
                    parent_url=url,
                    priority=self._calculate_external_priority(ext_url),
                    content_type_hint=self._detect_content_type(ext_url),
                )
                url_entries.append(entry)

            logger.info(f"Found {len(url_entries)} external links from {url}")
            return url_entries

        except Exception as e:
            logger.error(f"Failed to discover external links from {url}: {e}")
            return []

    def categorize_urls(self, urls: List[URLEntry]) -> Dict[str, List[URLEntry]]:
        """Categorize URLs by extraction method needed."""
        # Categorize URLs using list comprehension
        wordpress_urls = [
            u for u in urls if self._determine_extraction_method(u) == "wordpress"
        ]
        graphql_urls = [
            u for u in urls if self._determine_extraction_method(u) == "graphql"
        ]
        crawl4ai_urls = [
            u for u in urls if self._determine_extraction_method(u) == "crawl4ai"
        ]

        categories = {
            "wordpress": wordpress_urls,
            "graphql": graphql_urls,
            "crawl4ai": crawl4ai_urls,
        }

        logger.info(
            f"Categorized URLs: wordpress={len(wordpress_urls)}, "
            f"graphql={len(graphql_urls)}, crawl4ai={len(crawl4ai_urls)}"
        )

        return categories

    def _determine_extraction_method(self, url_entry: URLEntry) -> str:
        """Determine which extraction method to use for a URL."""
        url = url_entry.url.lower()

        # WordPress REST API endpoints
        if "/wp-json/" in url or "/wp-admin/" in url:
            return "wordpress"

        # GraphQL endpoints or authenticated content
        if "/graphql" in url or self._requires_authentication(url_entry):
            return "graphql"

        # Everything else goes to Crawl4AI (web pages, YouTube, documents, etc.)
        return "crawl4ai"

    def _requires_authentication(self, url_entry: URLEntry) -> bool:
        """Check if URL requires authentication (GraphQL)."""
        # This could be expanded based on URL patterns or metadata
        # For now, assume certain patterns require GraphQL
        url = url_entry.url.lower()

        auth_patterns = [
            "/members/",
            "/login/",
            "/dashboard/",
            "/admin/",
            "/private/",
            "/restricted/",
        ]

        return any(pattern in url for pattern in auth_patterns)

    def should_crawl_external(self, url: str) -> bool:
        """Check if external URL should be crawled."""
        if not getattr(self.config, "enable_external_crawling", True):
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check whitelist
        for whitelisted_domain in self.external_whitelist:
            if domain.endswith(whitelisted_domain.lower()):
                return True

        return False

    def _is_external_url(self, url: str) -> bool:
        """Check if URL is external to NEFAC."""
        parsed = urlparse(url)
        return not parsed.netloc.endswith("nefac.org")

    def _detect_content_type(self, url: str) -> str:
        """Detect content type from URL."""
        url_lower = url.lower()

        # Document files
        if any(re.search(pattern, url_lower) for pattern in self.document_patterns):
            return ContentType.DOCUMENT.value

        # Image files
        if any(re.search(pattern, url_lower) for pattern in self.image_patterns):
            return ContentType.IMAGE.value

        # Archive files
        if any(re.search(pattern, url_lower) for pattern in self.archive_patterns):
            return ContentType.ARCHIVE.value

        # YouTube videos
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return ContentType.YOUTUBE_VIDEO.value

        # API endpoints
        if any(pattern in url_lower for pattern in ["/api/", "/wp-json/", "/graphql"]):
            return ContentType.API_ENDPOINT.value

        # Default to web page
        return ContentType.WEB_PAGE.value

    def _calculate_external_priority(self, url: str) -> int:
        """Calculate priority for external URLs."""
        priority = 10  # Base priority for external links

        url_lower = url.lower()

        # High priority for government and legal sites
        if any(domain in url_lower for domain in ["gov", "court", "legal"]):
            priority += 30

        # Medium priority for documents
        if any(re.search(pattern, url_lower) for pattern in self.document_patterns):
            priority += 20

        # Medium priority for YouTube
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            priority += 15

        # Lower priority for images
        if any(re.search(pattern, url_lower) for pattern in self.image_patterns):
            priority -= 5

        return priority

    def filter_urls_by_freshness(
        self, urls: List[URLEntry], max_age_days: int = 30
    ) -> List[URLEntry]:
        """Filter URLs to only include fresh content."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        fresh_urls = []
        for url in urls:
            # If we don't have a discovery date, assume it's fresh
            if url.discovered_date >= cutoff_date:
                fresh_urls.append(url)

        logger.info(
            f"Filtered {len(urls)} URLs to {len(fresh_urls)} fresh URLs (max age: {max_age_days} days)"
        )
        return fresh_urls

    def deduplicate_urls(self, urls: List[URLEntry]) -> List[URLEntry]:
        """Remove duplicate URLs while preserving the highest priority entry."""
        url_map = {}

        for url_entry in urls:
            normalized_url = self._normalize_url(url_entry.url)

            if (
                normalized_url not in url_map
                or url_entry.priority > url_map[normalized_url].priority
            ):
                url_map[normalized_url] = url_entry

        deduplicated = list(url_map.values())
        logger.info(f"Deduplicated {len(urls)} URLs to {len(deduplicated)} unique URLs")

        return deduplicated

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove common URL parameters that don't affect content
        parsed = urlparse(url)

        # Remove fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # Remove trailing slash for consistency
        if normalized.endswith("/") and len(normalized) > 1:
            normalized = normalized[:-1]

        return normalized.lower()

    def get_discovery_stats(self, urls: List[URLEntry]) -> Dict:
        """Get statistics about discovered URLs."""
        stats = {
            "total_urls": len(urls),
            "by_source": {},
            "by_content_type": {},
            "by_domain": {},
            "by_priority": {"high": 0, "medium": 0, "low": 0},
            "external_urls": 0,
            "internal_urls": 0,
        }

        for url in urls:
            # By source
            stats["by_source"][url.source] = stats["by_source"].get(url.source, 0) + 1

            # By content type
            content_type = url.content_type_hint or "unknown"
            stats["by_content_type"][content_type] = (
                stats["by_content_type"].get(content_type, 0) + 1
            )

            # By domain
            domain = url.domain
            stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

            # By priority
            if url.priority >= 50:
                stats["by_priority"]["high"] += 1
            elif url.priority >= 20:
                stats["by_priority"]["medium"] += 1
            else:
                stats["by_priority"]["low"] += 1

            # External vs internal
            if url.is_external:
                stats["external_urls"] += 1
            else:
                stats["internal_urls"] += 1

        return stats

    def create_crawl_plan(
        self, urls: List[URLEntry], max_urls_per_batch: int = 100
    ) -> List[List[URLEntry]]:
        """Create batched crawl plan based on priorities and constraints."""
        # Sort by priority (highest first)
        sorted_urls = sorted(urls, key=lambda x: x.priority, reverse=True)

        # Create batches
        batches = []
        current_batch = []

        for url in sorted_urls:
            current_batch.append(url)

            if len(current_batch) >= max_urls_per_batch:
                batches.append(current_batch)
                current_batch = []

        # Add remaining URLs
        if current_batch:
            batches.append(current_batch)

        logger.info(f"Created crawl plan with {len(batches)} batches")
        return batches
