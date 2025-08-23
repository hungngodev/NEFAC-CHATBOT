"""
Metadata manager for NEFAC crawler.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

from src.schemas.metadata import BaseMetadata, DocumentMetadata, HTMLMetadata, PDFMetadata, XLSXMetadata, YouTubeMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.downloaders.common import JSONUtils

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages metadata saving and validation."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.metadata_dir = config.output_dir / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _filter_dict_for_dataclass(self, data_dict: Dict[str, Any], target_class) -> Dict[str, Any]:
        """Filter dictionary to only include fields that exist in the target dataclass."""
        if hasattr(target_class, "__dataclass_fields__"):
            # For dataclasses, get field names
            valid_fields = set(target_class.__dataclass_fields__.keys())
        elif hasattr(target_class, "model_fields"):
            # For Pydantic models, get field names
            valid_fields = set(target_class.model_fields.keys())
        else:
            # Fallback: return original dict
            return data_dict

        return {k: v for k, v in data_dict.items() if k in valid_fields}

    def _to_dict(self, obj):
        """Convert object to dict, handling both Pydantic models and dataclasses."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return dict(obj)

    def _prepare_doc_dict(self, doc: BaseMetadata) -> Dict[str, Any]:
        """Prepare document dictionary with required fields and fallbacks."""
        # Convert BaseMetadata to dict using model_dump if available, otherwise __dict__
        if hasattr(doc, "model_dump"):
            doc_dict = doc.model_dump(exclude_none=True)
        else:
            doc_dict = {k: v for k, v in doc.__dict__.items() if v is not None}

        # Ensure required fields are present with fallbacks
        if not doc_dict.get("id"):
            doc_dict["id"] = getattr(doc, "id", "unknown")
        if not doc_dict.get("title"):
            doc_dict["title"] = getattr(doc, "title", "Untitled Document")
        if not doc_dict.get("filename"):
            if hasattr(doc, "source_url") and doc.source_url:
                parsed = urlparse(doc.source_url)
                doc_dict["filename"] = parsed.path.split("/")[-1] or f"document_{doc_dict['id']}"
            else:
                doc_dict["filename"] = f"document_{doc_dict['id']}"
        if not doc_dict.get("source_url"):
            doc_dict["source_url"] = getattr(doc, "source_url", "")
        if not doc_dict.get("date"):
            doc_dict["date"] = getattr(doc, "date", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))

        # Add fields specific to HTMLMetadata
        if not doc_dict.get("slug"):
            title_val = doc_dict.get("title") or ""
            doc_dict["slug"] = title_val.lower().replace(" ", "-").replace("/", "-")[:50] or f"document-{doc_dict['id']}"
        if not doc_dict.get("file_path"):
            doc_dict["file_path"] = f"downloads/{doc_dict['filename']}"
        if not doc_dict.get("uri"):
            doc_dict["uri"] = doc_dict.get("source_url", f"/document/{doc_dict['id']}")
        if not doc_dict.get("link"):
            doc_dict["link"] = doc_dict.get("source_url", f"/document/{doc_dict['id']}")

        return doc_dict

    def _categorize_document(self, doc_dict: Dict[str, Any]) -> str:
        """Categorize document based on URL, mime type, and source."""
        source_url = doc_dict.get("source_url", "")
        mime_type = doc_dict.get("mime_type", "")
        source = doc_dict.get("source", "")

        if "pdf" in source_url.lower() or mime_type == "application/pdf":
            return "pdf"
        elif "xlsx" in source_url.lower() or "xls" in source_url.lower() or "spreadsheet" in mime_type.lower():
            return "xlsx"
        elif "html" in mime_type.lower() or "html" in source_url.lower():
            return "html"
        elif "youtube" in source.lower() or mime_type == "video/youtube":
            return "youtube"
        else:
            return "other"

    def _create_validated_metadata(self, doc_dict: Dict[str, Any], category: str):
        """Create validated metadata object based on category."""
        metadata_classes = {"pdf": PDFMetadata, "xlsx": XLSXMetadata, "html": HTMLMetadata, "youtube": YouTubeMetadata, "other": DocumentMetadata}

        target_class = metadata_classes[category]
        filtered_dict = self._filter_dict_for_dataclass(doc_dict, target_class)
        return target_class(**filtered_dict)

    def save_documents_metadata(self, documents: List[BaseMetadata]):
        """Save document metadata with schema validation to separate files by type."""
        pdf_documents: List[Dict[str, Any]] = []
        xlsx_documents: List[Dict[str, Any]] = []
        html_documents: List[Dict[str, Any]] = []
        youtube_documents: List[Dict[str, Any]] = []
        other_documents: List[Dict[str, Any]] = []

        document_lists = {"pdf": pdf_documents, "xlsx": xlsx_documents, "html": html_documents, "youtube": youtube_documents, "other": other_documents}

        for doc in documents:
            doc_dict = self._prepare_doc_dict(doc)
            category = self._categorize_document(doc_dict)

            validated_metadata = self._create_validated_metadata(doc_dict, category)
            document_lists[category].append(self._to_dict(validated_metadata))

        # Save to separate files by document type
        file_mappings = {"pdf": "pdf_metadata.json", "xlsx": "xlsx_metadata.json", "html": "html_metadata.json", "youtube": "youtube_metadata.json", "other": "documents_metadata.json"}

        for category, filename in file_mappings.items():
            docs = document_lists[category]
            if docs:
                file_path = self.metadata_dir / filename
                JSONUtils.save_to_file(docs, file_path)

    def save_youtube_metadata(self, youtube_videos: List[Dict[str, Any]]):
        """Save YouTube video metadata."""
        youtube_documents = []
        for video_data in youtube_videos:
            validated = YouTubeMetadata(**video_data)
            youtube_documents.append(validated.model_dump())

        youtube_file = self.metadata_dir / "youtube_metadata.json"
        JSONUtils.save_to_file(youtube_documents, youtube_file)

    def save_images_metadata(self):
        """Save metadata for images."""
        images_dir = self.config.output_dir / "images"
        if not images_dir.exists():
            return

        metadata_file = self.metadata_dir / "images_metadata.json"

        # Load existing metadata if it exists
        metadata_lookup = {}
        if metadata_file.exists():
            loaded_data = JSONUtils.load_from_file(metadata_file)
            if isinstance(loaded_data, dict):
                metadata_lookup = loaded_data

        images_metadata = []
        for image_file in images_dir.glob("**/*"):
            if image_file.is_file():
                images_metadata.append(self._create_image_metadata(image_file, metadata_lookup))

        JSONUtils.save_to_file(images_metadata, metadata_file)
        logger.info("Saved %d images metadata entries", len(images_metadata))

    def save_all_metadata(
        self,
        documents: List[BaseMetadata],
        youtube_videos: List[Dict[str, Any]] = None,
        crawl_result: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ):
        """Save comprehensive metadata for all sources."""
        logger.info("Saving comprehensive metadata...")

        # Save document metadata
        self.save_documents_metadata(documents)

        # Save YouTube metadata if provided
        if youtube_videos:
            self.save_youtube_metadata(youtube_videos)

        # Save images metadata
        self.save_images_metadata()

        # Save additional crawl metadata if provided
        if crawl_result or metadata:
            crawl_metadata_file = self.metadata_dir / "crawl_metadata.json"
            crawl_data = {
                "crawl_result": crawl_result or {},
                "metadata": metadata or {},
                "total_documents": len(documents),
                "youtube_videos": len(youtube_videos) if youtube_videos else 0,
            }
            JSONUtils.save_to_file(crawl_data, crawl_metadata_file)
            logger.info("Saved crawl metadata")

    def _create_image_metadata(self, image_file: Path, metadata_lookup: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata for an image file."""
        # Basic file information
        stat = image_file.stat()
        file_info = {
            "filename": image_file.name,
            "file_path": str(image_file.relative_to(self.config.output_dir)),
            "file_size": stat.st_size,
            "file_extension": image_file.suffix,
            "file_created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "file_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

        # Try to find matching metadata from documents
        potential_url = urljoin("https://nefac.org", f"/wp-content/uploads/{image_file.name}")
        matched_meta = metadata_lookup.get(potential_url)

        if matched_meta:
            # Merge with existing metadata
            full_meta = {**matched_meta, **file_info}
            full_meta["metadata_source"] = "merged_from_documents_metadata"
        else:
            # Create basic metadata
            full_meta = file_info
            full_meta.update(
                {
                    "title": image_file.stem,
                    "source_url": None,
                    "metadata_source": "generated_from_filesystem",
                }
            )

        return full_meta
