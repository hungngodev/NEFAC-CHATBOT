"""Common utility functions for the NEFAC crawler."""

import json
import logging
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


class JSONUtils:
    """Utility functions for JSON operations."""

    @staticmethod
    def safe_dump(data: Any, indent: int = 2) -> str:
        """Safely serialize data to JSON string."""
        try:
            return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Error serializing to JSON: {e}")
            return "{}"

    @staticmethod
    def safe_load(json_str: str) -> Any:
        """Safely deserialize JSON string to data."""
        try:
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error deserializing JSON: {e}")
            return {}

    @staticmethod
    def save_to_file(data: Any, filepath: Union[str, Path]) -> bool:
        """Save data to JSON file."""
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {filepath}: {e}")
            return False

    @staticmethod
    def save_json(data: Any, filepath: Union[str, Path]) -> bool:
        """Save data to JSON file (alias for save_to_file)."""
        return JSONUtils.save_to_file(data, filepath)

    @staticmethod
    def load_from_file(filepath: Union[str, Path]) -> Any:
        """Load data from JSON file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON from {filepath}: {e}")
            return {}

    @staticmethod
    def load_json(filepath: Union[str, Path]) -> Any:
        """Load data from JSON file (alias for load_from_file)."""
        return JSONUtils.load_from_file(filepath)


class DateUtils:
    """Utility functions for date and time operations."""

    @staticmethod
    def now_iso() -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def get_current_iso_string() -> str:
        """Get current timestamp in ISO format (alias for now_iso)."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """Parse various date string formats."""
        if not date_str:
            return None

        # Common date formats to try (including microseconds)
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO format with microseconds and timezone
            "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format UTC with microseconds
            "%Y-%m-%dT%H:%M:%SZ",  # ISO format UTC
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds, no timezone
            "%Y-%m-%dT%H:%M:%S",  # ISO format without timezone
            "%Y-%m-%d %H:%M:%S",  # Standard datetime
            "%Y-%m-%d",  # Date only
            "%d/%m/%Y",  # DD/MM/YYYY
            "%m/%d/%Y",  # MM/DD/YYYY
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    @staticmethod
    def format_date(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format datetime object to string."""
        try:
            return dt.strftime(format_str)
        except Exception as e:
            logger.error(f"Error formatting date {dt}: {e}")
            return ""

    @staticmethod
    def extract_year_from_date(date_str: str) -> str:
        """Extract year from date string."""
        if not date_str:
            return ""

        parsed_date = DateUtils.parse_date(date_str)
        if parsed_date:
            return str(parsed_date.year)

        # Try to extract year with regex as fallback
        year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if year_match:
            return year_match.group()

        return ""


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
    def calculate_file_hash(content: bytes) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def safe_filename(filename: str) -> str:
        """Create a safe filename by removing/replacing invalid characters."""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove multiple consecutive underscores
        filename = re.sub(r"_+", "_", filename)
        # Limit length
        if len(filename) > 255:
            name, ext = Path(filename).stem, Path(filename).suffix
            filename = name[: 255 - len(ext)] + ext
        return filename.strip("_")

    @staticmethod
    def generate_file_id(url: str, content_hash: Optional[str] = None) -> str:
        """Generate a unique file ID from URL and optional content hash."""
        # Create a base ID from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        if content_hash:
            # Use first 8 chars of content hash if available
            return f"{url_hash}_{content_hash[:8]}"
        else:
            # Use URL hash only
            return url_hash

    @staticmethod
    def generate_safe_filename(filename: str) -> str:
        """Generate a safe filename (alias for safe_filename)."""
        return FileUtils.safe_filename(filename)

    @staticmethod
    def extract_title_from_url(url: str) -> str:
        """Extract a meaningful title from URL."""
        if not url:
            return "unknown"

        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            # Get the last part of the path
            if path:
                parts = path.split("/")
                last_part = parts[-1]

                # Remove file extension
                if "." in last_part:
                    last_part = ".".join(last_part.split(".")[:-1])

                # Clean up the title
                title = last_part.replace("-", " ").replace("_", " ")
                title = re.sub(r"\s+", " ", title).strip()

                if title:
                    return title

            # Fallback to domain name
            domain = parsed.netloc.replace("www.", "")
            return domain or "unknown"

        except Exception as e:
            logger.error(f"Error extracting title from URL {url}: {e}")
            return "unknown"

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

        extension = extension.lower().lstrip(".")

        document_types = {"pdf", "doc", "docx", "txt", "rtf", "odt"}
        spreadsheet_types = {"xls", "xlsx", "csv", "ods"}
        presentation_types = {"ppt", "pptx", "odp"}
        image_types = {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "avif"}
        video_types = {"mp4", "avi", "mov", "wmv", "flv", "webm"}
        audio_types = {"mp3", "wav", "flac", "aac", "ogg"}
        archive_types = {"zip", "rar", "7z", "tar", "gz"}

        if extension in document_types:
            return "document"
        elif extension in spreadsheet_types:
            return "spreadsheet"
        elif extension in presentation_types:
            return "presentation"
        elif extension in image_types:
            return "image"
        elif extension in video_types:
            return "video"
        elif extension in audio_types:
            return "audio"
        elif extension in archive_types:
            return "archive"
        else:
            return "other"

    @staticmethod
    def get_filename_from_url(url: str) -> str:
        """Extract filename from URL."""
        if not url:
            return "unknown"

        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")

            if path:
                # Get the last part of the path which should be the filename
                filename = path.split("/")[-1]

                # If there's a filename with extension, return it
                if "." in filename and not filename.endswith("."):
                    return filename

                # Otherwise, generate a meaningful name
                if filename:
                    return filename

            # Fallback to generating from URL
            domain = parsed.netloc.replace("www.", "")
            return f"{domain}_file" if domain else "unknown_file"

        except Exception as e:
            logger.error(f"Error extracting filename from URL {url}: {e}")
            return "unknown_file"


class TextUtils:
    """Utility functions for text processing."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text.strip())
        # Remove control characters
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        return text

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        return re.findall(url_pattern, text)

    @staticmethod
    def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def extract_keywords(text: str, min_length: int = 3) -> List[str]:
        """Extract potential keywords from text."""
        if not text:
            return []

        # Simple keyword extraction (can be enhanced with NLP)
        words = re.findall(r"\b[a-zA-Z]{" + str(min_length) + r",}\b", text.lower())
        # Remove common stop words
        stop_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "day",
            "get",
            "has",
            "him",
            "his",
            "how",
            "its",
            "may",
            "new",
            "now",
            "old",
            "see",
            "two",
            "who",
            "boy",
            "did",
            "she",
            "use",
            "way",
            "will",
        }
        keywords = [word for word in words if word not in stop_words]
        # Return unique keywords
        return list(set(keywords))

    @staticmethod
    def clean_html(html: str) -> str:
        """Clean HTML content by removing tags and normalizing text."""
        if not html:
            return ""

        # Remove script and style tags completely
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML tags but keep the content
        html = re.sub(r"<[^>]+>", " ", html)

        # Decode HTML entities
        html = html.replace("&nbsp;", " ")
        html = html.replace("&amp;", "&")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&quot;", '"')
        html = html.replace("&#39;", "'")

        # Clean up whitespace
        html = re.sub(r"\s+", " ", html.strip())

        return html


class ValidationUtils:
    """Utility functions for data validation."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if a string is a valid URL."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Check if a string is a valid email address."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def clean_url(url: str, base_url: str = "") -> str:
        """Clean and normalize URL."""
        if not url:
            return ""

        url = url.strip()

        # Handle relative URLs
        if url.startswith("/") and base_url:
            url = urljoin(base_url, url)
        elif not url.startswith(("http://", "https://")) and base_url:
            url = urljoin(base_url, url)

        # Remove fragment identifiers
        if "#" in url:
            url = url.split("#")[0]

        return url

    @staticmethod
    def validate_document_info(doc_info: Dict[str, Any]) -> bool:
        """Validate document information structure."""
        required_fields = ["id", "title", "source_url"]
        return all(field in doc_info and doc_info[field] for field in required_fields)

    @staticmethod
    def sanitize_html(html: str) -> str:
        """Basic HTML sanitization (remove script tags, etc.)."""
        if not html:
            return ""

        # Remove script and style tags
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        return html

    @staticmethod
    def is_document_type_supported(mime_type: str) -> bool:
        """Check if a MIME type represents a supported document type."""
        if not mime_type:
            return False

        mime_type = mime_type.lower().strip()

        # Supported document MIME types
        supported_types = {
            # PDF documents
            "application/pdf",
            # Microsoft Office documents
            "application/msword",  # .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
            "application/vnd.ms-excel",  # .xls
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
            "application/vnd.ms-powerpoint",  # .ppt
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
            # Text documents
            "text/plain",  # .txt
            "text/rtf",  # .rtf
            "application/rtf",  # .rtf (alternative)
            # OpenDocument formats
            "application/vnd.oasis.opendocument.text",  # .odt
            "application/vnd.oasis.opendocument.spreadsheet",  # .ods
            "application/vnd.oasis.opendocument.presentation",  # .odp
            # Other useful formats
            "text/csv",  # .csv
            "application/json",  # .json
            "application/xml",  # .xml
            "text/xml",  # .xml
        }

        return mime_type in supported_types
