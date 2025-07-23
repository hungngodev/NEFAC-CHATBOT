"""
Document downloader for NEFAC crawler.
"""

import logging
import mimetypes
from datetime import datetime
from pathlib import Path

import PyPDF2
import requests

from ..core.config import CrawlerConfig
from ..core.types import DocumentInfo
from ..utils.common import DateUtils, FileUtils

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """Handles downloading and validation of documents."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.quarantine_count = 0
        self._session = None

    def get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "NEFAC-Crawler/3.0"})
        return self._session

    def download(self, document_info: DocumentInfo) -> bool:
        """Download a document file and validate it."""
        if not self.config.download_files:
            return True

        try:
            # Generate file path
            filepath = self._generate_filepath(document_info)

            # Skip if file already exists
            if filepath.exists():
                logger.debug(f"File already exists: {filepath}")
                self._update_document_metadata(document_info, filepath)
                return True

            # Download the file
            success = self._download_file(document_info, filepath)
            if success:
                # Validate the downloaded file
                self._validate_document(filepath, document_info)
                # Update metadata
                self._update_document_metadata(document_info, filepath)

            return success

        except Exception as e:
            logger.error(f"Failed to download {document_info.title}: {e}")
            return False

    def get_quarantine_count(self) -> int:
        """Get number of quarantined documents."""
        return self.quarantine_count

    def _generate_filepath(self, document_info: DocumentInfo) -> Path:
        """Generate file path for the document."""
        filename = self._generate_filename(document_info)

        # Determine directory based on file type
        file_extension = Path(filename).suffix.lower()

        if file_extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
            return self.config.output_dir / "images" / filename
        elif file_extension == ".html":
            return self.config.output_dir / "content" / filename
        else:
            # Organize documents by year
            year = DateUtils.extract_year_from_date(document_info.date)
            return self.config.output_dir / "documents" / year / filename

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

        # Default to pdf
        return "pdf"

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
            session = self.get_session()
            response = session.get(source_url, timeout=self.config.download_timeout, stream=True)
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

    def _validate_document(self, filepath: Path, document_info: DocumentInfo):
        """Validate downloaded document and quarantine if corrupted."""
        if filepath.suffix.lower() != ".pdf":
            return  # Only validate PDFs for now

        try:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if len(reader.pages) > 0:
                    document_info.validation_status = "valid"
                    return

            # Check if encrypted
            if PyPDF2.PdfReader(filepath).is_encrypted:
                logger.warning(f"PDF is encrypted: {filepath}")
                document_info.validation_status = "encrypted"
                return

        except Exception as e:
            logger.error(f"Corrupted document detected: {filepath}. Reason: {e}")
            document_info.validation_status = "corrupted"

            # Move to quarantine
            quarantine_dir = self.config.output_dir / "quarantine"
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            quarantine_path = quarantine_dir / filepath.name

            try:
                filepath.rename(quarantine_path)
                logger.info(f"Moved corrupted file to quarantine: {quarantine_path}")
                self.quarantine_count += 1
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

            # File classification
            extension = filepath.suffix.lower()
            document_info.file_extension = extension
            document_info.file_type_category = FileUtils.get_file_type_category(extension)
            document_info.is_image = extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]
            document_info.is_document = extension in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt"]
            document_info.is_archive = extension in [".zip", ".rar", ".7z", ".tar", ".gz"]
