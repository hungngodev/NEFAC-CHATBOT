"""
Metadata manager for NEFAC crawler.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

# Import Pydantic models directly from schemas
from src.schemas.metadata import ContentMetadata, PDFMetadata, YouTubeMetadata

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import DocumentInfo
from src.service.crawler.utils.common import JSONUtils

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
                    # Use Pydantic model directly
                    validated = PDFMetadata(**doc_dict)
                    pdf_documents.append(validated.model_dump())
                elif doc.mime_type == "text/html" or doc.file_extension == ".html":
                    # Use Pydantic model directly
                    validated = ContentMetadata(**doc_dict)
                    content_documents.append(validated.model_dump())
                else:
                    # Default to PDFMetadata for other document types
                    # Use Pydantic model directly
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
        logger.info("Saving YouTube metadata for %d videos...", len(youtube_videos))

        youtube_documents = []
        for video_data in youtube_videos:
            try:
                # Use Pydantic model directly
                validated = YouTubeMetadata(**video_data)
                youtube_documents.append(validated.model_dump())
            except Exception as e:
                logger.error(
                    "YouTube metadata validation failed for %s: %s",
                    video_data.get("title", "Unknown"),
                    e,
                )
                # Still save the video but mark validation failure
                youtube_documents.append(video_data)

        # Save to file
        try:
            youtube_file = self.metadata_dir / "youtube_metadata.json"
            JSONUtils.save_to_file(youtube_documents, youtube_file)
            logger.info("Saved YouTube metadata for %d videos", len(youtube_documents))
        except Exception as e:
            logger.error("Failed to save YouTube metadata: %s", e)

    def save_images_metadata(self):
        """Save metadata for images."""
        logger.info("Saving images metadata...")

        try:
            images_dir = self.config.output_dir / "images"
            if not images_dir.exists():
                logger.debug("No images directory found - skipping image metadata")
                return

            metadata_file = self.metadata_dir / "images_metadata.json"

            # Load existing metadata if it exists
            metadata_lookup = {}
            if metadata_file.exists():
                try:
                    loaded_data = JSONUtils.load_json(metadata_file)
                    # Ensure it's a dict
                    if isinstance(loaded_data, dict):
                        metadata_lookup = loaded_data
                    else:
                        logger.warning(
                            "Loaded metadata is not a dict, using empty dict"
                        )
                except Exception as e:
                    logger.warning("Failed to load existing image metadata: %s", e)

            images_metadata = []
            for image_file in images_dir.glob("**/*"):
                if image_file.is_file():
                    images_metadata.append(
                        self._create_image_metadata(image_file, metadata_lookup)
                    )

            JSONUtils.save_json(images_metadata, metadata_file)
            logger.info("Saved %d images metadata entries", len(images_metadata))

        except Exception as e:
            logger.error("Failed to save images metadata: %s", e)

    def save_all_metadata(
        self,
        documents: List[DocumentInfo],
        youtube_videos: List[Dict[str, Any]] = None,
        crawl_result: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ):
        """Save comprehensive metadata for all sources."""
        logger.info("Saving comprehensive metadata...")

        try:
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
                JSONUtils.save_json(crawl_data, crawl_metadata_file)
                logger.info("Saved crawl metadata")

        except Exception as e:
            logger.error("Failed to save comprehensive metadata: %s", e)

    def _document_info_to_dict(self, doc_info: DocumentInfo) -> Dict[str, Any]:
        """Convert DocumentInfo to dictionary for metadata saving."""
        # Start with a clean copy of the document info
        doc_dict = doc_info.__dict__.copy()

        # Ensure all required BaseMetadata fields are present
        if "id" not in doc_dict or doc_dict["id"] is None:
            doc_dict["id"] = getattr(doc_info, "id", "unknown")

        if "title" not in doc_dict or doc_dict["title"] is None:
            doc_dict["title"] = getattr(doc_info, "title", "Untitled Document")

        if "filename" not in doc_dict or doc_dict["filename"] is None:
            # Generate filename from URL or ID
            if hasattr(doc_info, "source_url") and doc_info.source_url:
                from urllib.parse import urlparse

                parsed = urlparse(doc_info.source_url)
                doc_dict["filename"] = (
                    parsed.path.split("/")[-1] or f"document_{doc_info.id}"
                )
            else:
                doc_dict["filename"] = f"document_{doc_info.id}"

        if "source_url" not in doc_dict or doc_dict["source_url"] is None:
            doc_dict["source_url"] = getattr(doc_info, "source_url", "")

        if "date" not in doc_dict or doc_dict["date"] is None:
            # Use current date as fallback
            from datetime import datetime

            doc_dict["date"] = getattr(
                doc_info, "date", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            )

        # Add required ContentMetadata fields that might be missing
        if "slug" not in doc_dict or doc_dict["slug"] is None:
            # Generate slug from title or URL
            if doc_dict.get("title"):
                doc_dict["slug"] = (
                    doc_dict["title"].lower().replace(" ", "-").replace("/", "-")[:50]
                )
            else:
                doc_dict["slug"] = f"document-{doc_info.id}"

        if "file_path" not in doc_dict or doc_dict["file_path"] is None:
            # Generate file_path from filename
            doc_dict["file_path"] = f"downloads/{doc_dict['filename']}"

        if "uri" not in doc_dict or doc_dict["uri"] is None:
            # Use source_url as URI
            doc_dict["uri"] = doc_dict.get("source_url", f"/document/{doc_info.id}")

        if "link" not in doc_dict or doc_dict["link"] is None:
            # Use source_url as link
            doc_dict["link"] = doc_dict.get("source_url", f"/document/{doc_info.id}")

        # Remove None values (except for the required fields we just set)
        return {k: v for k, v in doc_dict.items() if v is not None}

    def _create_image_metadata(
        self, image_file: Path, metadata_lookup: Dict[str, Any]
    ) -> Dict[str, Any]:
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
        potential_url = urljoin(
            "https://nefac.org", f"/wp-content/uploads/{image_file.name}"
        )
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
