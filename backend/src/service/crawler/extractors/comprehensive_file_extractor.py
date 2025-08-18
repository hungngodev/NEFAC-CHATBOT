"""
Enhanced File Extractor for NEFAC Crawler
Handles ALL file types except images - PDFs, Excel, Word, etc.
Works with the comprehensive discovery engine to ensure no files are missed.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, unquote


# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import (
    ExtractorResult,
    URLEntry,
    CrawlerSource,
    DocumentInfo,
)
from src.service.crawler.utils.session_manager import SessionManager
from src.service.crawler.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class ComprehensiveFileExtractor(BaseExtractor):
    """
    Extract ALL types of files from NEFAC website.
    Discovers and processes every document, spreadsheet, presentation, etc., emitting DocumentInfo objects for the main crawler to handle.
    """

    def __init__(self, config: CrawlerConfig):
        super().__init__(config)  # Call BaseExtractor.__init__
        self.session = SessionManager.get_default_session()

        # File types we want to extract (everything except images)
        self.target_file_types = {
            ".pdf": "PDF Document",
            ".doc": "Word Document (Legacy)",
            ".docx": "Word Document",
            ".xls": "Excel Spreadsheet (Legacy)",
            ".xlsx": "Excel Spreadsheet",
            ".ppt": "PowerPoint (Legacy)",
            ".pptx": "PowerPoint Presentation",
            ".csv": "CSV Data",
            ".txt": "Text File",
            ".rtf": "Rich Text Format",
            ".odt": "OpenDocument Text",
            ".ods": "OpenDocument Spreadsheet",
            ".odp": "OpenDocument Presentation",
            ".zip": "ZIP Archive",
            ".json": "JSON Data",
            ".xml": "XML Data",
            ".rss": "RSS Feed",
            ".atom": "Atom Feed",
            ".epub": "EPUB Book",
            ".mobi": "MOBI Book",
        }

        # Image types to exclude (as requested)
        self.excluded_image_types = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".svg",
            ".bmp",
            ".ico",
            ".tiff",
            ".tif",
        }

        # MIME types we want
        self.target_mime_types = {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/csv",
            "text/plain",
            "application/rtf",
            "application/zip",
            "application/json",
            "application/xml",
            "text/xml",
            "application/rss+xml",
            "application/atom+xml",
        }

    @property
    def source_name(self) -> str:
        return CrawlerSource.CONTENT_EXTRACTION.value

    def extract(self, url_entries: Optional[List[URLEntry]] = None) -> ExtractorResult:
        """
        Extract ALL files from the provided URLs.
        Processes every document and emits DocumentInfo objects for the main crawler to handle downloading and organization.
        """
        if url_entries is None:
            url_entries = []

        logger.info(
            f"Starting comprehensive file extraction for {len(url_entries)} URLs..."
        )

        # Log initial PDF count
        initial_pdf_count = sum(
            1 for url in url_entries if url.lower().endswith(".pdf")
        )
        logger.info(f"Initial PDF count in discovery: {initial_pdf_count}")

        # Filter to only file URLs
        file_urls = self._filter_file_urls(url_entries)
        logger.info(f"📄 Found {len(file_urls)} file URLs to process")

        # Extract files in batches
        extracted_files = []
        failed_extractions = []
        warnings = []

        batch_size = 5
        for i in range(0, len(file_urls), batch_size):
            batch = file_urls[i : i + batch_size]
            valid_documents = []

            for url_entry in batch:
                try:
                    result = self._extract_single_file(url_entry)
                    if result:
                        valid_documents.append(result)
                    else:
                        failed_extractions.append(url_entry.url)
                except Exception as e:
                    logger.error(f"Failed to extract {url_entry.url}: {e}")
                    failed_extractions.append(url_entry.url)

                # Respectful delay
                time.sleep(0.3)

            # Log batch statistics
            batch_pdf_count = sum(
                1 for doc in valid_documents if doc.mime_type == "application/pdf"
            )
            rate = len(batch) / (time.time() - i)
            logger.info(
                f"Extraction batch {i//batch_size + 1} completed. Processed {len(batch)} URLs. "
                f"Valid files: {len(valid_documents)} (PDFs: {batch_pdf_count}). "
                f"Rate: {rate:.1f} URLs/sec"
            )

            extracted_files.extend(valid_documents)

            # Progress update
            processed = min(i + batch_size, len(file_urls))
            logger.info(
                f"📄 Processed {processed}/{len(file_urls)} files, {len(extracted_files)} successful"
            )

        # Create ExtractorResult object
        result = ExtractorResult(
            documents=extracted_files,
            warnings=warnings,
            errors=failed_extractions,
            metadata={
                "total_urls_processed": len(url_entries),
                "file_urls_found": len(file_urls),
                "files_extracted": len(extracted_files),
                "failed_extractions": len(failed_extractions),
                "file_types_extracted": self._get_file_type_breakdown(extracted_files),
                "failed_urls": failed_extractions,
                "extraction_timestamp": time.time(),
                "source": "comprehensive_file_extractor",
            },
        )

        logger.info(
            f"✅ File extraction complete: {len(extracted_files)} files extracted"
        )
        self._log_extraction_summary(result)

        return result

    def _filter_file_urls(self, url_entries: List[URLEntry]) -> List[URLEntry]:
        """Filter URLs to only include downloadable files (not images)."""
        file_urls = []

        for url_entry in url_entries:
            url_lower = url_entry.url.lower()

            # Check if it matches our target file extensions
            if any(url_lower.endswith(ext) for ext in self.target_file_types.keys()):
                # Make sure it's not an image
                if not any(
                    url_lower.endswith(img_ext) for img_ext in self.excluded_image_types
                ):
                    file_urls.append(url_entry)

        return file_urls

    def _extract_single_file(self, url_entry: URLEntry):
        """Extract a single file and return DocumentInfo object."""
        try:
            url = url_entry.url
            logger.debug(f"Processing file: {url}")

            # Get file metadata
            mime_type = self._get_mime_type(url)
            file_size = self._get_file_size(url)
            title = self._extract_title_from_url(url)
            content_category = self._categorize_content(url, title)

            # Validate file type
            parsed_url = urlparse(url)
            file_extension = Path(parsed_url.path).suffix.lower()

            # Skip if it's an image
            if file_extension in self.excluded_image_types:
                logger.debug(f"Skipping image file: {url}")
                return None

            # Create filename
            filename = Path(parsed_url.path).name or f"document_{int(time.time())}"
            if not Path(filename).suffix and mime_type:
                # Try to infer extension from MIME type
                ext_map = {
                    "application/pdf": ".pdf",
                    "application/msword": ".doc",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                    "application/vnd.ms-excel": ".xls",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
                    "text/csv": ".csv",
                    "text/plain": ".txt",
                }
                if mime_type in ext_map:
                    filename += ext_map[mime_type]

            # Create DocumentInfo object (no actual download)
            document_info = self._create_document_info(
                id_value=f"file_{hash(url) % 1000000}",
                title=title,
                source_url=url,
                mime_type=mime_type or "application/octet-stream",
                date=(
                    url_entry.discovered_date.isoformat()
                    if url_entry.discovered_date
                    else None
                ),
                filename=filename,
                file_size=file_size,
                metadata={
                    "content_category": content_category,
                    "priority": url_entry.priority,
                },
            )

            logger.info(
                f"✅ Prepared metadata for: {filename} ({file_size or 'unknown size'})"
            )

            return document_info

        except Exception as e:
            logger.error(f"❌ Failed to extract file {url_entry.url}: {e}")
            return None

    def _get_mime_type(self, url: str) -> Optional[str]:
        """Get MIME type from URL headers."""
        try:
            head_response = self.session.head(url, timeout=10, allow_redirects=True)
            return head_response.headers.get("content-type", "").split(";")[0].lower()
        except Exception as e:
            logger.error(f"Failed to get MIME type for {url}: {e}")
            return None

    def _get_file_size(self, url: str) -> Optional[int]:
        """Get file size from URL headers."""
        try:
            head_response = self.session.head(url, timeout=10, allow_redirects=True)
            content_length = head_response.headers.get("content-length")
            return (
                int(content_length)
                if content_length and content_length.isdigit()
                else None
            )
        except Exception as e:
            logger.error(f"Failed to get file size for {url}: {e}")
            return None

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from the URL."""
        parsed_url = urlparse(url)
        filename = parsed_url.path.split("/")[-1]

        if filename:
            # Remove extension and decode
            name = unquote(filename)
            if "." in name:
                name = name.rsplit(".", 1)[0]

            # Clean up the name
            name = name.replace("_", " ").replace("-", " ")
            return name.title()

        return "Document"

    def _categorize_content(self, url: str, title: Optional[str]) -> str:
        """Categorize content based on URL and title."""
        url_lower = url.lower()
        title_lower = (title or "").lower()

        # FOIA-related content
        if any(
            term in url_lower or term in title_lower
            for term in ["foia", "freedom-of-information", "public-records"]
        ):
            return "FOIA Resources"

        # News content
        if any(
            term in url_lower for term in ["/news/", "/press-release", "/announcement"]
        ):
            return "News & Press"

        # Legal cases
        if any(
            term in url_lower or term in title_lower
            for term in ["case", "court", "legal", "ruling"]
        ):
            return "Legal Cases"

        # Legislation
        if any(
            term in url_lower or term in title_lower
            for term in ["legislation", "bill", "law", "statute"]
        ):
            return "Legislation"

        # Resources and guides
        if any(
            term in url_lower or term in title_lower
            for term in ["guide", "resource", "how-to", "tip"]
        ):
            return "Resources & Guides"

        # Reports and studies
        if any(
            term in url_lower or term in title_lower
            for term in ["report", "study", "analysis", "survey"]
        ):
            return "Reports & Studies"

        return "General Documents"

    def _get_file_type_breakdown(self, documents: List[DocumentInfo]) -> Dict[str, int]:
        """Get breakdown of extracted files by type."""
        breakdown = {}
        for doc in documents:
            # Get file type from metadata if available, otherwise use mime_type
            file_type = doc.metadata.get(
                "file_type",
                doc.mime_type.split("/")[-1] if doc.mime_type else "Unknown",
            )
            breakdown[file_type] = breakdown.get(file_type, 0) + 1
        return breakdown

    def _log_extraction_summary(self, result: ExtractorResult) -> None:
        """Log comprehensive extraction summary."""
        metadata = result.metadata

        logger.info("📄 FILE EXTRACTION SUMMARY")
        logger.info("=" * 40)
        logger.info(f"Total URLs Processed: {metadata['total_urls_processed']:,}")
        logger.info(f"File URLs Found: {metadata['file_urls_found']:,}")
        logger.info(f"Files Successfully Extracted: {metadata['files_extracted']:,}")
        logger.info(f"Failed Extractions: {metadata['failed_extractions']:,}")

        if metadata["file_types_extracted"]:
            logger.info("\n📊 File Types Extracted:")
            for file_type, count in sorted(
                metadata["file_types_extracted"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                logger.info(f"   {file_type}: {count:,} files")

        # Show content categories
        category_breakdown = {}
        for doc in result.documents:
            # Get content category from metadata if available
            category = (
                doc.metadata.get("content_category", "Unknown")
                if hasattr(doc, "metadata")
                else "Unknown"
            )
            category_breakdown[category] = category_breakdown.get(category, 0) + 1

        if category_breakdown:
            logger.info("\n🏷️  Content Categories:")
            for category, count in sorted(
                category_breakdown.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"   {category}: {count:,} files")

        logger.info("=" * 40)
