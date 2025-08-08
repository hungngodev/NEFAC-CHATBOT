"""Document downloader for NEFAC crawler."""

from __future__ import annotations
import logging
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import PyPDF2
import requests

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import DocumentInfo
from src.service.crawler.utils.common import DateUtils, FileUtils
from src.service.crawler.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """Handles downloading and validation of documents."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.quarantine_count = 0
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        """Get or create HTTP session with default headers."""
        if self._session is None:
            self._session = SessionManager.get_default_session()
        return self._session

    def download(self, document_info: DocumentInfo) -> bool:
        """Download and validate a document file."""
        if not self.config.download_files:
            return True

        try:
            filepath = self._generate_filepath(document_info)

            if filepath.exists():
                logger.debug("File exists: %s", filepath)
                self._update_document_metadata(document_info, filepath)
                return True

            if self._download_file(document_info, filepath):
                if self._validate_downloaded_file(filepath, document_info):
                    self._update_document_metadata(document_info, filepath)
                    return True
                else:
                    logger.warning("Validation failed for %s", filepath)
                    return False
            return False

        except Exception as e:
            logger.error("Download failed for %s: %s", document_info.source_url, e)
            return False

    def download_document(self, document_info: DocumentInfo) -> bool:
        """Alias for download method to maintain backward compatibility."""
        return self.download(document_info)

    def get_quarantine_count(self) -> int:
        """Get number of quarantined documents."""
        return self.quarantine_count

    def _get_file_type_dir(self, extension: str) -> Path:
        """Get the appropriate directory for a file type based on extension."""
        # Import the file type mapping from config
        from src.service.crawler.core.config import FILE_TYPE_DIRECTORIES

        # Normalize extension (ensure it starts with .)
        if not extension.startswith("."):
            extension = f".{extension}"
        extension = extension.lower()

        # Get directory from mapping, default to 'other' if not found
        dir_name = FILE_TYPE_DIRECTORIES.get(extension, "other")

        return self.config.output_dir / dir_name

    def _generate_filepath(self, document_info: DocumentInfo) -> Path:
        """Generate file path for the document."""
        filename = self._generate_filename(document_info)
        ext = Path(filename).suffix.lower()

        # Special handling for YouTube content
        if (
            document_info.mime_type == "video/youtube"
            or "youtube" in document_info.source.lower()
        ):
            return self.config.output_dir / "youtube" / filename

        # Special handling for HTML/web content
        if document_info.mime_type and "html" in document_info.mime_type.lower():
            return self.config.output_dir / "html" / filename

        # Use extension-based directory mapping for all other files
        base_dir = self._get_file_type_dir(ext)
        return base_dir / filename

    def _generate_filename(self, document_info: DocumentInfo) -> str:
        """Generate a meaningful filename for the document."""
        title = document_info.title or "Unknown Document"
        date = document_info.date or ""
        mime_type = document_info.mime_type or ""
        source = document_info.source or "unknown"

        # Extract year from date
        year = DateUtils.extract_year_from_date(date)

        # Get file extension from MIME type or URL
        extension = self._get_file_extension(mime_type, document_info.source_url)

        # Generate safe filename from title
        if title and title != "Unknown Document":
            clean_title = FileUtils.generate_safe_filename(title)
        else:
            # Generate from URL or use generic name
            if document_info.source_url:
                clean_title = FileUtils.extract_title_from_url(document_info.source_url)
                clean_title = FileUtils.generate_safe_filename(clean_title)
            else:
                clean_title = f"document_{source.replace('_', '-')}"

        # Add source identifier for non-standard sources
        if source not in ["wordpress_rest_api", "graphql_api", "graphql_authenticated"]:
            clean_title = f"{clean_title}_{source.replace('_', '-')}"

        # Ensure we have a valid filename
        if not clean_title:
            clean_title = f"document_{year}"

        return f"{clean_title}.{extension}"

    def _get_file_extension(self, mime_type: str, source_url: str) -> str:
        """Get file extension from MIME type or URL."""
        # Handle HTML content specifically
        if mime_type and "html" in mime_type.lower():
            return "html"

        # Try to get extension from MIME type first
        if mime_type:
            extension = mimetypes.guess_extension(mime_type)
            if extension:
                return extension[1:]  # Remove the dot

        # Try to get extension from URL
        if source_url:
            url_ext = Path(source_url).suffix.lower()
            if url_ext:
                return url_ext[1:]  # Remove the dot
            # Try to guess MIME type from URL as fallback
            guessed_mime_type = FileUtils.guess_mime_type(source_url)
            if guessed_mime_type and guessed_mime_type != "application/octet-stream":
                extension = mimetypes.guess_extension(guessed_mime_type)
                if extension:
                    return extension[1:]  # Remove the dot

        # Default to html for web content
        return "html"

    def save_html_content(self, document_info: DocumentInfo, content: str) -> bool:
        """Save HTML content to the html folder."""
        try:
            filepath = self._generate_filepath(document_info)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Save the HTML content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Update document metadata
            self._update_document_metadata(document_info, filepath)

            logger.debug(f"HTML content saved: {filepath}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to save HTML content for {document_info.source_url}: {e}"
            )
            return False

    def _download_file(self, document_info: DocumentInfo, filepath: Path) -> bool:
        """Download file from URL."""
        source_url = document_info.source_url
        if not source_url or source_url.lower() == "none":
            logger.warning("Missing or invalid source URL")
            return False

        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Download file
            session = self.session
            response = session.get(
                source_url, timeout=self.config.download_timeout, stream=True
            )
            response.raise_for_status()

            # Update MIME type from response if available
            content_type = response.headers.get("content-type")
            if content_type:
                document_info.mime_type = content_type

            # Write file
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug(f"Successfully downloaded: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Download failed for {source_url}: {e}")
            return False

    def download_documents(self, documents: List[DocumentInfo]) -> List[DocumentInfo]:
        """Download content for documents that need it."""
        logger.info(f"Starting download of {len(documents)} documents")

        # Filter documents that need downloading
        docs_to_download = [doc for doc in documents if not doc.content and doc.url]
        docs_to_skip = [doc for doc in documents if doc.content or not doc.url]

        downloaded_docs = []
        failed_downloads = 0

        # Download documents that need content
        for doc in docs_to_download:
            try:
                # Determine download method based on content type
                content_type = doc.metadata.get("content_type", "text")
                content = self._download_by_type(doc.url, content_type)

                # Update document with downloaded content
                doc.content = content
                downloaded_docs.append(doc)

            except Exception as e:
                logger.error(f"Failed to download document {doc.id}: {e}")
                failed_downloads += 1
                # Still include the document even if download failed
                downloaded_docs.append(doc)

        # Combine skipped and downloaded documents
        result_docs = docs_to_skip + downloaded_docs

        logger.info(
            f"Download complete. Success: {len(downloaded_docs) - failed_downloads}, Failed: {failed_downloads}"
        )
        return result_docs

    def _download_by_type(self, url: str, content_type: str) -> str:
        """Download content based on the content type."""
        if content_type == "text":
            return self._download_text(url)
        elif content_type == "pdf":
            return self._download_pdf(url)
        else:
            # Default to text download for unknown types
            logger.warning(
                f"Unknown content type '{content_type}', defaulting to text download"
            )
            return self._download_text(url)

    def _validate_downloaded_file(self, file_path: str, doc: DocumentInfo) -> bool:
        """Validate downloaded file integrity and format with enhanced checks."""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File not found after download: {file_path}")
                return False

            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.warning(f"Downloaded file is empty: {file_path}")
                return False

            # Check minimum file size (100 bytes as minimum for a valid document)
            if file_size < 100:
                logger.warning(
                    f"Downloaded file too small ({file_size} bytes): {file_path}"
                )
                return False

            # Validate based on file type
            mime_type = doc.mime_type.lower() if doc.mime_type else ""

            if "pdf" in mime_type:
                return self._validate_pdf_file(file_path)
            elif any(
                word_type in mime_type for word_type in ["word", "document", "msword"]
            ):
                return self._validate_word_file(file_path)
            elif any(
                excel_type in mime_type for excel_type in ["excel", "spreadsheet"]
            ):
                return self._validate_excel_file(file_path)
            elif any(
                ppt_type in mime_type for ppt_type in ["powerpoint", "presentation"]
            ):
                return self._validate_powerpoint_file(file_path)
            elif "text" in mime_type or "csv" in mime_type:
                return self._validate_text_file(file_path)
            elif any(
                archive_type in mime_type
                for archive_type in ["zip", "rar", "7z", "tar"]
            ):
                return self._validate_archive_file(file_path)
            else:
                # For other file types, just check if file exists and has content
                # Additional check: try to read first few bytes to ensure it's not corrupted
                try:
                    with open(file_path, "rb") as f:
                        header = f.read(1024)  # Read first 1KB
                        if not header:
                            logger.warning(
                                f"File appears to be corrupted (empty header): {file_path}"
                            )
                            return False
                except Exception as read_error:
                    logger.warning(f"Cannot read file {file_path}: {read_error}")
                    return False
                return file_size > 0

        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}")
            return False

    def _validate_pdf_file(self, file_path: str) -> bool:
        try:
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                if pdf_reader.is_encrypted:
                    try:
                        pdf_reader.decrypt("")
                    except Exception:
                        pass
                # Try to read first page to verify PDF is valid
                if len(pdf_reader.pages) > 0:
                    _ = pdf_reader.pages[0].extract_text()
            logger.debug("Validated PDF: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid PDF file: {file_path}. Error: {e}")
            return False

    def _validate_word_file(self, file_path: str) -> bool:
        try:
            # Simple validation for Word files, can be enhanced with more checks
            with open(file_path, "rb") as f:
                header = f.read(1024)  # Read first 1KB
                if not header:
                    logger.warning(
                        f"File appears to be corrupted (empty header): {file_path}"
                    )
                    return False
            logger.debug("Validated Word file: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid Word file: {file_path}. Error: {e}")
            return False

    def _validate_excel_file(self, file_path: str) -> bool:
        try:
            # Simple validation for Excel files, can be enhanced with more checks
            with open(file_path, "rb") as f:
                header = f.read(1024)  # Read first 1KB
                if not header:
                    logger.warning(
                        f"File appears to be corrupted (empty header): {file_path}"
                    )
                    return False
            logger.debug("Validated Excel file: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid Excel file: {file_path}. Error: {e}")
            return False

    def _validate_powerpoint_file(self, file_path: str) -> bool:
        try:
            # Simple validation for PowerPoint files, can be enhanced with more checks
            with open(file_path, "rb") as f:
                header = f.read(1024)  # Read first 1KB
                if not header:
                    logger.warning(
                        f"File appears to be corrupted (empty header): {file_path}"
                    )
                    return False
            logger.debug("Validated PowerPoint file: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid PowerPoint file: {file_path}. Error: {e}")
            return False

    def _validate_text_file(self, file_path: str) -> bool:
        try:
            # Simple validation for text files, can be enhanced with more checks
            with open(file_path, "r") as f:
                content = f.read(1024)  # Read first 1KB
                if not content:
                    logger.warning(
                        f"File appears to be corrupted (empty content): {file_path}"
                    )
                    return False
            logger.debug("Validated text file: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid text file: {file_path}. Error: {e}")
            return False

    def _validate_archive_file(self, file_path: str) -> bool:
        try:
            # Simple validation for archive files, can be enhanced with more checks
            with open(file_path, "rb") as f:
                header = f.read(1024)  # Read first 1KB
                if not header:
                    logger.warning(
                        f"File appears to be corrupted (empty header): {file_path}"
                    )
                    return False
            logger.debug("Validated archive file: %s", file_path)
            return True
        except Exception as e:
            logger.warning(f"Invalid archive file: {file_path}. Error: {e}")
            return False
            self.quarantine_count += 1
            raise

    def _move_to_quarantine(self, filepath: Path):
        """Move a file to the quarantine directory."""
        try:
            quarantine_dir = self.config.output_dir / "quarantine"
            quarantine_dir.mkdir(exist_ok=True)
            quarantine_path = quarantine_dir / filepath.name
            if filepath.exists():
                filepath.rename(quarantine_path)
                logger.info(f"Moved corrupted file to quarantine: {quarantine_path}")
        except OSError as move_error:
            logger.error(f"Failed to move corrupted file to quarantine: {move_error}")

    def _update_document_metadata(self, document_info: DocumentInfo, filepath: Path):
        """Update document metadata with file information."""
        if filepath.exists():
            stat = filepath.stat()
            document_info.file_size = stat.st_size
            document_info.file_path = str(filepath.relative_to(self.config.output_dir))
            document_info.filename = filepath.name
            document_info.download_date = DateUtils.get_current_iso_string()
            document_info.processing_timestamp = datetime.now().timestamp()
            document_info.crawler_version = "3.0"

            extension = filepath.suffix.lower()
            document_info.file_extension = extension
            document_info.file_type_category = FileUtils.get_file_type_category(
                extension
            )
