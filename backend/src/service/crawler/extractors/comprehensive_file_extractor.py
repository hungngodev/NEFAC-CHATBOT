"""
Enhanced File Extractor for NEFAC Crawler
Handles ALL file types except images - PDFs, Excel, Word, etc.
Works with the comprehensive discovery engine to ensure no files are missed.
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, unquote


# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import ExtractionResult, URLEntry, CrawlerSource
from src.service.crawler.utils.session_manager import SessionManager
from src.service.crawler.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class ComprehensiveFileExtractor(BaseExtractor):
    """
    Extract ALL types of files from NEFAC website.
    Downloads and processes every document, spreadsheet, presentation, etc.
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

    def extract(self, url_entries: Optional[List[URLEntry]] = None) -> ExtractionResult:
        """
        Extract ALL files from the provided URLs.
        Downloads every document and processes metadata.
        """
        if url_entries is None:
            url_entries = []

        logger.info(
            f"🔍 Starting comprehensive file extraction for {len(url_entries)} URLs"
        )

        # Filter to only file URLs
        file_urls = self._filter_file_urls(url_entries)
        logger.info(f"📄 Found {len(file_urls)} file URLs to process")

        # Extract files in batches
        extracted_files = []
        failed_extractions = []

        batch_size = 5
        for i in range(0, len(file_urls), batch_size):
            batch = file_urls[i : i + batch_size]

            for url_entry in batch:
                try:
                    result = self._extract_single_file(url_entry)
                    if result:
                        extracted_files.append(result)
                    else:
                        failed_extractions.append(url_entry.url)
                except Exception as e:
                    logger.error(f"Failed to extract {url_entry.url}: {e}")
                    failed_extractions.append(url_entry.url)

                # Respectful delay
                time.sleep(0.3)

            # Progress update
            processed = min(i + batch_size, len(file_urls))
            logger.info(
                f"📄 Processed {processed}/{len(file_urls)} files, {len(extracted_files)} successful"
            )

        # Create comprehensive result
        result = ExtractionResult(
            documents=extracted_files,
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

    def _extract_single_file(self, url_entry: URLEntry) -> Optional[Dict]:
        """Extract a single file and return document metadata."""
        url = url_entry.url

        try:
            # First, check if we can access the file
            head_response = self.session.head(url, timeout=10, allow_redirects=True)

            # Get content type and size
            content_type = (
                head_response.headers.get("content-type", "").split(";")[0].lower()
            )
            content_length = head_response.headers.get("content-length")
            file_size = (
                int(content_length)
                if content_length and content_length.isdigit()
                else None
            )

            # Skip if it's too large (>50MB)
            if file_size and file_size > 50 * 1024 * 1024:
                logger.warning(
                    f"Skipping large file {url} ({file_size / (1024*1024):.1f}MB)"
                )
                return None

            # Get file extension and type
            parsed_url = urlparse(url)
            file_path = unquote(parsed_url.path)
            file_extension = (
                "." + file_path.split(".")[-1].lower() if "." in file_path else ""
            )

            # Verify it's a file type we want
            if (
                file_extension not in self.target_file_types
                and content_type not in self.target_mime_types
            ):
                return None

            # Create document metadata
            document_metadata = {
                "url": url,
                "title": getattr(url_entry, "title", None)
                or self._extract_title_from_url(url),
                "file_extension": file_extension,
                "file_type": self.target_file_types.get(file_extension, "Unknown"),
                "content_type": content_type,
                "file_size": file_size,
                "source": url_entry.source or "file_discovery",
                "priority": url_entry.priority or 3,
                "last_modified": getattr(url_entry, "last_modified", None),
                "discovery_timestamp": time.time(),
                "content_category": self._categorize_content(
                    url, getattr(url_entry, "title", None)
                ),
                "download_url": url,
            }

            # If configured to download files, download them
            if self.config.download_files:
                local_path = self._download_file(url, file_extension)
                if local_path:
                    document_metadata["local_path"] = str(local_path)
                    document_metadata["file_size_actual"] = local_path.stat().st_size

            # Extract text content if possible
            if file_extension in [".txt", ".csv", ".json", ".xml", ".rss", ".atom"]:
                text_content = self._extract_text_content(url)
                if text_content:
                    document_metadata["text_content"] = text_content[
                        :10000
                    ]  # Limit size
                    document_metadata["text_preview"] = text_content[:500]

            return document_metadata

        except Exception as e:
            logger.error(f"Error extracting file {url}: {e}")
            return None

    def _download_file(self, url: str, file_extension: str) -> Optional[Path]:
        """Download file to local storage."""
        try:
            # Create download directory
            download_dir = self.config.output_dir / "downloaded_files"
            download_dir.mkdir(parents=True, exist_ok=True)

            # Generate safe filename
            parsed_url = urlparse(url)
            filename = parsed_url.path.split("/")[-1]
            if not filename or "." not in filename:
                filename = f"file_{hash(url) % 100000}{file_extension}"

            # Ensure filename is safe
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
            if not safe_filename.endswith(file_extension):
                safe_filename += file_extension

            file_path = download_dir / safe_filename

            # Download file
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)

            logger.debug(f"Downloaded {url} to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    def _extract_text_content(self, url: str) -> Optional[str]:
        """Extract text content from text-based files."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Try to decode as text
            try:
                return response.text
            except UnicodeDecodeError:
                # Try different encodings
                for encoding in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        return response.content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return None

        except Exception as e:
            logger.error(f"Failed to extract text from {url}: {e}")
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

    def _get_file_type_breakdown(self, documents: List[Dict]) -> Dict[str, int]:
        """Get breakdown of extracted files by type."""
        breakdown = {}
        for doc in documents:
            file_type = doc.get("file_type", "Unknown")
            breakdown[file_type] = breakdown.get(file_type, 0) + 1
        return breakdown

    def _log_extraction_summary(self, result: ExtractionResult) -> None:
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
            category = doc.get("content_category", "Unknown")
            category_breakdown[category] = category_breakdown.get(category, 0) + 1

        if category_breakdown:
            logger.info("\n🏷️  Content Categories:")
            for category, count in sorted(
                category_breakdown.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"   {category}: {count:,} files")

        logger.info("=" * 40)
