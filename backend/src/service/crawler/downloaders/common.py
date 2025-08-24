"""Common utility functions for the NEFAC crawler."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class JSONUtils:
    """Utility functions for JSON operations."""

    # Note: keep only file-based helpers actually used across the codebase.

    @staticmethod
    def save_to_file(data: Any, filepath: str | Path) -> bool:
        """Save data to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True

    @staticmethod
    def load_from_file(filepath: str | Path) -> Any:
        """Load data from JSON file."""
        filepath = Path(filepath)
        if not filepath.exists():
            return {}

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


class DateUtils:
    """Utility functions for date and time operations."""

    @staticmethod
    def get_current_iso_string() -> str:
        """Get current timestamp in ISO format (alias for now_iso)."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        """Parse various date string formats."""
        if not date_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            parsed_date = DateUtils._try_parse_date(date_str.strip(), fmt)
            if parsed_date:
                return parsed_date
        return None

    @staticmethod
    def _try_parse_date(date_str: str, fmt: str) -> datetime | None:
        """Try to parse date with given format."""
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            return None

    @staticmethod
    def extract_year_from_date(date_str: str) -> str:
        """Extract year from date string."""
        if not date_str:
            return ""

        parsed_date = DateUtils.parse_date(date_str)
        if parsed_date:
            return str(parsed_date.year)

        year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
        return year_match.group() if year_match else ""


class FileUtils:
    """Utility functions for file operations."""

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension from filename."""
        return Path(filename).suffix.lower().lstrip(".")

    @staticmethod
    def get_mime_type_from_extension(extension: str) -> str:
        """Get MIME type from file extension."""
        mime_types = {
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "txt": "text/plain",
            "html": "text/html",
            "htm": "text/html",
            "css": "text/css",
            "js": "application/javascript",
            "json": "application/json",
            "xml": "application/xml",
            "zip": "application/zip",
            "rar": "application/x-rar-compressed",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "mp4": "video/mp4",
            "avi": "video/x-msvideo",
            "mov": "video/quicktime",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
        }
        return mime_types.get(extension.lower(), "application/octet-stream")

    @staticmethod
    def safe_filename(filename: str) -> str:
        """Create a safe filename by removing/replacing invalid characters."""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Replace spaces with hyphens for better filename compatibility
        filename = filename.replace(" ", "-")
        # Remove multiple consecutive underscores or hyphens
        filename = re.sub(r"[-_]+", lambda m: "-" if "-" in m.group() else "_", filename)
        # Limit length
        if len(filename) > 255:
            name, ext = Path(filename).stem, Path(filename).suffix
            filename = name[: 255 - len(ext)] + ext
        return filename.strip("_-")

    @staticmethod
    def generate_safe_filename(filename: str) -> str:
        """Generate a safe filename (alias for safe_filename)."""
        return FileUtils.safe_filename(filename)

    @staticmethod
    def extract_title_from_url(url: str) -> str:
        """Extract a meaningful title from URL."""
        if not url:
            return "unknown"

        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if path:
            parts = path.split("/")
            last_part = parts[-1]
            if "." in last_part:
                last_part = ".".join(last_part.split(".")[:-1])
            title = last_part.replace("-", " ").replace("_", " ")
            title = re.sub(r"\s+", " ", title).strip()
            if title:
                return title

        return parsed.netloc.replace("www.", "") or "unknown"

    @staticmethod
    def guess_mime_type(url: str) -> str:
        """Guess MIME type from URL extension."""
        if not url:
            return "application/octet-stream"

        extension = FileUtils.get_file_extension(url)
        return FileUtils.get_mime_type_from_extension(extension)

    @staticmethod
    def get_file_type_category(extension: str) -> str:
        """Get file type category from extension."""
        if not extension:
            return "other"

        ext = extension.lower().lstrip(".")
        categories = {
            "document": {"pdf", "doc", "docx", "txt", "rtf", "odt"},
            "spreadsheet": {"xls", "xlsx", "csv", "ods"},
            "presentation": {"ppt", "pptx", "odp"},
            "image": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "avif"},
            "video": {"mp4", "avi", "mov", "wmv", "flv", "webm"},
            "audio": {"mp3", "wav", "flac", "aac", "ogg"},
            "archive": {"zip", "rar", "7z", "tar", "gz"},
        }

        for category, extensions in categories.items():
            if ext in extensions:
                return category
        return "other"

    # Note: TextUtils helpers were removed as they were unused in the codebase.


class ValidationUtils:
    """Utility functions for data validation."""

    @staticmethod
    def is_document_type_supported(mime_type: str) -> bool:
        """Check if a MIME type represents a supported document type."""
        if not mime_type:
            return False

        mime_type = mime_type.lower().strip()
        supported_types = {
            "application/pdf",
            "application/msword",
            "text/plain",
            "text/csv",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/rtf",
            "application/rtf",
            "application/json",
            "application/xml",
            "text/xml",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.presentation",
        }

        return mime_type in supported_types
