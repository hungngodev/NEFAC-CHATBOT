"""
Web scraper extractor for document discovery from NEFAC website.
Implements comprehensive web scraping with document link extraction.
"""

import logging
import re
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from ..core.config import CrawlerConfig
from ..core.types import CrawlerSource, DocumentInfo, ExtractorResult
from .base import BaseExtractor, RequestMixin

logger = logging.getLogger(__name__)


class WebScraperExtractor(BaseExtractor, RequestMixin):
    """Web scraper for discovering document links from web pages."""

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)
        self.session = self.get_session()

        # Document link patterns (from legacy)
        self.document_patterns = [
            r'href=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|txt|rtf|odt|ods|odp))["\']',
            r'href=["\']([^"\']*(?:uploads|files|documents|attachments)[^"\']*)["\']',
            r'href=["\']([^"\']*download[^"\']*)["\']',
        ]

        # Specific NEFAC URL patterns
        self.nefac_patterns = [
            r'https?://(?:www\.)?nefac\.org/[^"\'>\s]*\.(?:pdf|doc|docx)',
            r'https?://(?:www\.)?nefac\.org/[^"\'>\s]*(?:uploads|files|documents)',
        ]

    @property
    def source_name(self) -> str:
        return CrawlerSource.WEB_SCRAPING.value

    def extract(self) -> ExtractorResult:
        """Extract documents from web scraping."""
        self._log_extraction_start()

        result = ExtractorResult(documents=[])

        try:
            documents = self._scrape_all_pages()
            result.documents = documents
        except Exception as e:
            error_msg = f"Error in web scraping: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_extraction_result(result)
        return result

    def _scrape_all_pages(self) -> List[DocumentInfo]:
        """Scrape all configured pages for documents."""
        logger.info("Starting web scraping for document discovery...")

        documents = []

        # Scrape main NEFAC pages for document links
        pages_to_scrape = [
            self.config.wordpress_base_url,
            f"{self.config.wordpress_base_url}/resources",
            f"{self.config.wordpress_base_url}/publications",
            f"{self.config.wordpress_base_url}/news",
            f"{self.config.wordpress_base_url}/events",
            f"{self.config.wordpress_base_url}/about",
        ]

        for page_url in pages_to_scrape:
            try:
                page_docs = self._scrape_web_pages_for_documents(page_url)
                documents.extend(page_docs)
                logger.info(f"Found {len(page_docs)} documents on {page_url}")

                # Rate limiting
                time.sleep(self.config.request_delay)

            except Exception as e:
                logger.error(f"Failed to scrape {page_url}: {e}")

        # Remove duplicates
        unique_documents = self._remove_duplicates(documents)
        logger.info(f"Web scraping completed. Found {len(unique_documents)} unique documents")

        return unique_documents

    def _scrape_web_pages_for_documents(self, url: str) -> List[DocumentInfo]:
        """Scrape a web page for document links."""
        documents = []

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            content = response.text

            # Extract document links using patterns
            document_links = self._extract_documents_from_content(content, url)

            for link_url, link_text in document_links:
                try:
                    doc_info = self._create_document_info(link_url, link_text, url)
                    if doc_info:
                        documents.append(doc_info)
                except Exception as e:
                    logger.warning(f"Failed to create document info for {link_url}: {e}")

        except Exception as e:
            logger.error(f"Failed to scrape page {url}: {e}")

        return documents

    def _extract_documents_from_content(self, content: str, base_url: str) -> List[tuple]:
        """Extract document links from HTML content."""
        document_links = []

        # Apply document patterns
        for pattern in self.document_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                link_url = match.group(1)

                # Convert relative URLs to absolute
                if not link_url.startswith(("http://", "https://")):
                    link_url = urljoin(base_url, link_url)

                # Extract link text (simplified)
                link_text = self._extract_link_text(content, match.start(), match.end())

                document_links.append((link_url, link_text))

        # Apply NEFAC-specific patterns
        for pattern in self.nefac_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                link_url = match.group(0)
                link_text = self._extract_link_text(content, match.start(), match.end())
                document_links.append((link_url, link_text))

        return list(set(document_links))  # Remove duplicates

    def _extract_link_text(self, content: str, start_pos: int, end_pos: int) -> str:
        """Extract the text associated with a link."""
        # Find the surrounding <a> tag and extract its text
        # This is a simplified version - the legacy had more complex logic

        # Look backwards for opening <a> tag
        search_start = max(0, start_pos - 200)
        a_tag_start = content.rfind("<a", search_start, start_pos)

        if a_tag_start != -1:
            # Find the closing > of the <a> tag
            a_tag_end = content.find(">", a_tag_start)
            if a_tag_end != -1:
                # Find the closing </a> tag
                a_close = content.find("</a>", a_tag_end)
                if a_close != -1:
                    # Extract text between tags
                    link_text = content[a_tag_end + 1 : a_close]
                    # Clean up the text
                    link_text = re.sub(r"<[^>]+>", "", link_text)  # Remove HTML tags
                    link_text = " ".join(link_text.split())  # Normalize whitespace
                    return link_text[:100]  # Limit length

        return "Document"  # Default

    def _create_document_info(self, url: str, title: str, source_page: str) -> Optional[DocumentInfo]:
        """Create DocumentInfo from URL and metadata."""
        try:
            parsed_url = urlparse(url)
            filename = parsed_url.path.split("/")[-1]

            if not filename:
                return None

            # Extract file extension
            file_extension = filename.split(".")[-1].lower() if "." in filename else ""

            # Determine MIME type
            mime_type = self._get_mime_type_from_extension(file_extension)

            return self._create_document_info(id_value=f"web-{hash(url)}", title=title or filename, source_url=url, mime_type=mime_type, date="", file_extension=file_extension, filename=filename, description=f"Found on: {source_page}")  # Will be determined during download

        except Exception as e:
            logger.error(f"Error creating document info for {url}: {e}")
            return None

    def _get_mime_type_from_extension(self, extension: str) -> str:
        """Get MIME type from file extension."""
        mime_map = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "txt": "text/plain",
            "rtf": "application/rtf",
            "odt": "application/vnd.oasis.opendocument.text",
            "ods": "application/vnd.oasis.opendocument.spreadsheet",
            "odp": "application/vnd.oasis.opendocument.presentation",
        }
        return mime_map.get(extension, "application/octet-stream")

    def _remove_duplicates(self, documents: List[DocumentInfo]) -> List[DocumentInfo]:
        """Remove duplicate documents based on source URL."""
        seen_urls = set()
        unique_documents = []

        for doc in documents:
            if doc.source_url not in seen_urls:
                seen_urls.add(doc.source_url)
                unique_documents.append(doc)

        return unique_documents
