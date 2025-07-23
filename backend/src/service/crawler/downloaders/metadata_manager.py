"""
Metadata manager for NEFAC crawler.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from src.schemas.state import ContentMetadata, PDFMetadata, YouTubeMetadata

from ..core.config import CrawlerConfig
from ..core.types import DocumentInfo
from ..utils.common import JSONUtils

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages metadata saving and validation."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.metadata_dir = config.output_dir / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def save_documents_metadata(self, documents: List[DocumentInfo]):
        """Save document metadata with schema validation."""
        logger.info("Saving document metadata...")

        # Separate documents by type
        pdf_documents = []
        content_documents = []
        other_documents = []

        for doc in documents:
            doc_dict = self._document_info_to_dict(doc)

            try:
                if doc.mime_type == "application/pdf" or doc.file_extension == ".pdf":
                    validated = PDFMetadata(**doc_dict)
                    pdf_documents.append(validated.model_dump())
                elif doc.mime_type == "text/html" or doc.file_extension == ".html":
                    validated = ContentMetadata(**doc_dict)
                    content_documents.append(validated.model_dump())
                else:
                    # Default to PDFMetadata for other document types
                    validated = PDFMetadata(**doc_dict)
                    other_documents.append(validated.model_dump())

            except Exception as e:
                logger.error(f"Schema validation failed for document {doc.id}: {e}")
                # Still save the document but mark validation failure
                doc_dict["validation_error"] = str(e)
                other_documents.append(doc_dict)

        # Save to separate files
        if pdf_documents or other_documents:
            all_docs = pdf_documents + other_documents
            documents_file = self.metadata_dir / "documents_metadata.json"
            JSONUtils.save_json(all_docs, documents_file)
            logger.info(f"Saved {len(all_docs)} document metadata entries")

        if content_documents:
            content_file = self.metadata_dir / "content_metadata.json"
            JSONUtils.save_json(content_documents, content_file)
            logger.info(f"Saved {len(content_documents)} content metadata entries")

    def save_youtube_metadata(self, youtube_videos: List[Dict[str, Any]]):
        """Save YouTube video metadata."""
        if not youtube_videos:
            return

        logger.info("Saving YouTube metadata...")

        validated_videos = []
        for video in youtube_videos:
            try:
                validated = YouTubeMetadata(**video)
                validated_videos.append(validated.model_dump())
            except Exception as e:
                logger.error(f"YouTube metadata validation failed: {e}")
                # Save anyway but mark validation error
                video["validation_error"] = str(e)
                validated_videos.append(video)

        youtube_file = self.metadata_dir / "youtube_metadata.json"
        JSONUtils.save_json(validated_videos, youtube_file)
        logger.info(f"Saved {len(validated_videos)} YouTube metadata entries")

    def save_images_metadata(self):
        """Scan images folder and generate comprehensive metadata."""
        logger.info("Generating metadata for images...")

        images_dir = self.config.output_dir / "images"
        if not images_dir.exists():
            return

        images_metadata = []

        # Load existing document metadata for cross-reference
        documents_file = self.metadata_dir / "documents_metadata.json"
        doc_metadata = JSONUtils.load_json(documents_file) or []

        # Create lookup by source URL
        metadata_lookup = {item["source_url"]: item for item in doc_metadata if isinstance(item, dict) and "source_url" in item}

        # Process all image files
        for image_file in images_dir.glob("**/*"):
            if not image_file.is_file():
                continue

            try:
                file_info = self._create_image_metadata(image_file, metadata_lookup)
                images_metadata.append(file_info)
            except Exception as e:
                logger.error(f"Failed to process image {image_file}: {e}")

        if images_metadata:
            images_file = self.metadata_dir / "images_metadata.json"
            JSONUtils.save_json(images_metadata, images_file)
            logger.info(f"Saved metadata for {len(images_metadata)} images")

    def _document_info_to_dict(self, doc_info: DocumentInfo) -> Dict[str, Any]:
        """Convert DocumentInfo to dictionary for metadata saving."""
        # Use dataclass conversion if available, otherwise manual conversion
        if hasattr(doc_info, "__dict__"):
            return {k: v for k, v in doc_info.__dict__.items() if v is not None}

        # Manual conversion for compatibility
        return {
            "id": doc_info.id,
            "title": doc_info.title,
            "source_url": doc_info.source_url,
            "mime_type": doc_info.mime_type,
            "date": doc_info.date,
            "modified": doc_info.modified,
            "alt_text": doc_info.alt_text,
            "description": doc_info.description,
            "caption": doc_info.caption,
            "source": doc_info.source,
            "file_size": doc_info.file_size,
            "file_path": doc_info.file_path,
            "filename": doc_info.filename,
            "download_date": doc_info.download_date,
            "processing_timestamp": doc_info.processing_timestamp,
            "crawler_version": doc_info.crawler_version,
            "http_status_code": doc_info.http_status_code,
            "http_headers": doc_info.http_headers,
            "file_extension": doc_info.file_extension,
            "file_type_category": doc_info.file_type_category,
            "is_image": doc_info.is_image,
            "is_document": doc_info.is_document,
            "is_archive": doc_info.is_archive,
            "validation_status": doc_info.validation_status,
        }

    def _create_image_metadata(self, image_file: Path, metadata_lookup: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata for an image file."""
        from datetime import datetime
        from urllib.parse import urljoin

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
            full_meta.update({"title": image_file.stem, "source_url": None, "metadata_source": "generated_from_filesystem"})

        return full_meta
