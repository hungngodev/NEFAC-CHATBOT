"""
Utility functions for the NEFAC crawler.
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urljoin, urlparse

from ..core.config import DOCUMENT_EXTENSIONS, DOCUMENT_TYPES

logger = logging.getLogger(__name__)


class FileUtils:
    """Utilities for file operations."""

    @staticmethod
    def get_filename_from_url(url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = path.split("/")[-1]
            if filename:
                return filename
        return "unknown_file"

    @staticmethod
    def extract_title_from_url(url: str) -> str:
        """Extract a title from a document URL."""
        filename = FileUtils.get_filename_from_url(url)
        if filename and filename != "unknown_file":
            # Remove extension and clean up
            title = filename.rsplit(".", 1)[0]
            # Replace underscores and hyphens with spaces
            title = title.replace("_", " ").replace("-", " ")
            # Capitalize words
            title = " ".join(word.capitalize() for word in title.split())
            return title
        return "Unknown Document"

    @staticmethod
    def guess_mime_type(url: str) -> str:
        """Guess MIME type from file extension in URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1].lower()

        mime_map = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".csv": "text/csv",
            ".txt": "text/plain",
            ".rtf": "application/rtf",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".ods": "application/vnd.oasis.opendocument.spreadsheet",
            ".odp": "application/vnd.oasis.opendocument.presentation",
        }
        return mime_map.get(ext, "application/octet-stream")

    @staticmethod
    def get_file_type_category(extension: str) -> str:
        """Categorize file types."""
        if extension.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
            return "image"
        elif extension.lower() in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt"]:
            return "document"
        elif extension.lower() in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            return "archive"
        elif extension.lower() in [".html", ".htm"]:
            return "web_page"
        else:
            return "other"

    @staticmethod
    def is_document_url(url: str) -> bool:
        """Check if a URL points to a document."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in DOCUMENT_EXTENSIONS)

    @staticmethod
    def generate_safe_filename(title: str, max_length: int = 80) -> str:
        """Generate a safe filename from a title."""
        if not title or title == "Unknown Document":
            return "untitled"

        # Remove special characters but keep spaces and hyphens
        clean_title = re.sub(r"[^\w\s\-_.]", "", title)
        # Replace multiple spaces/hyphens with single
        clean_title = re.sub(r"[-\s]+", "-", clean_title)
        # Remove leading/trailing hyphens
        clean_title = clean_title.strip("-")
        # Limit length
        return clean_title[:max_length]


class TextUtils:
    """Utilities for text processing."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text."""
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text

    @staticmethod
    def clean_html(html_content: str) -> str:
        """Clean HTML content by removing tags and normalizing text."""
        if not html_content:
            return ""

        # Remove HTML tags
        clean_text = re.sub(r"<[^>]+>", "", html_content)
        # Decode HTML entities
        import html

        clean_text = html.unescape(clean_text)
        # Normalize whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        return clean_text

    @staticmethod
    def extract_title_from_html(html_content: str) -> str:
        """Extract title from HTML content."""
        try:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # Clean up the title
                title = re.sub(r"\s+", " ", title)
                return title
        except Exception:
            pass
        return "Untitled"

    @staticmethod
    def extract_documents_from_content(content: str, base_url: str) -> List[str]:
        """Extract document URLs from HTML content."""
        document_patterns = [
            r'href=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']',
            r'src=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']',
        ]

        documents = []
        for pattern in document_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.startswith("http"):
                    documents.append(match)
                else:
                    documents.append(urljoin(base_url, match))

        return list(set(documents))  # Remove duplicates


class JSONUtils:
    """Utilities for JSON operations."""

    @staticmethod
    def save_json(data: Any, filepath: Path, indent: int = 2) -> None:
        """Save data to JSON file."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
            logger.info(f"Saved JSON data to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save JSON to {filepath}: {e}")
            raise

    @staticmethod
    def load_json(filepath: Path) -> Optional[Any]:
        """Load data from JSON file."""
        try:
            if not filepath.exists():
                logger.warning(f"JSON file not found: {filepath}")
                return None

            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load JSON from {filepath}: {e}")
            return None


class DateUtils:
    """Utilities for date operations."""

    @staticmethod
    def get_current_iso_string() -> str:
        """Get current datetime as ISO string."""
        return datetime.now().isoformat()

    @staticmethod
    def now_iso() -> str:
        """Get current datetime as ISO string (alias for compatibility)."""
        return datetime.now().isoformat()

    @staticmethod
    def extract_year_from_date(date_str: str) -> str:
        """Extract year from date string."""
        if date_str and len(date_str) >= 4:
            return date_str[:4]
        return "unknown"


class ValidationUtils:
    """Utilities for validation operations."""

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate if a URL is valid."""
        if not url:
            return False
        return url.startswith(("http://", "https://", "file://"))

    @staticmethod
    def is_document_type_supported(mime_type: str) -> bool:
        """Check if the MIME type is supported."""
        return any(doc_type in mime_type for doc_type in DOCUMENT_TYPES.keys())


class LoggingUtils:
    """Utilities for logging operations."""

    @staticmethod
    def setup_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
        """Set up a logger with consistent formatting."""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Clear existing handlers
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger
