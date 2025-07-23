"""
WordPress REST API extractor for NEFAC documents.
"""

import logging
from typing import Dict, List

from ..core.config import ENDPOINTS
from ..core.types import CrawlerSource, DocumentInfo, ExtractorResult
from ..utils.common import ValidationUtils
from .base import BaseExtractor, PaginationMixin, RequestMixin

logger = logging.getLogger(__name__)


class WordPressExtractor(BaseExtractor, RequestMixin, PaginationMixin):
    """Extractor for WordPress REST API."""

    @property
    def source_name(self) -> str:
        return CrawlerSource.WORDPRESS_REST_API.value

    def extract(self) -> ExtractorResult:
        """Extract documents from WordPress REST API."""
        self._log_extraction_start()

        result = ExtractorResult(documents=[])

        try:
            # Extract media documents
            media_docs = self._extract_media_documents()
            result.documents.extend(media_docs)

            # Extract post attachments
            post_docs = self._extract_post_attachments()
            result.documents.extend(post_docs)

            # Extract news attachments
            news_docs = self._extract_news_attachments()
            result.documents.extend(news_docs)

        except Exception as e:
            error_msg = f"Error in WordPress extraction: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_extraction_result(result)
        return result

    def _extract_media_documents(self) -> List[DocumentInfo]:
        """Extract document media items from WordPress REST API."""
        logger.info("Fetching media items from WordPress REST API...")

        documents = []
        media_items = self.fetch_paginated(ENDPOINTS["media"])

        for item in media_items:
            if not self._is_document_media(item):
                continue

            try:
                doc_info = self._create_media_document_info(item)
                documents.append(doc_info)
            except Exception as e:
                logger.warning(f"Failed to process media item {item.get('id')}: {e}")

        logger.info(f"Found {len(documents)} media documents via WordPress REST API")
        return documents

    def _extract_post_attachments(self) -> List[DocumentInfo]:
        """Extract document attachments from posts."""
        logger.info("Extracting document attachments from posts...")

        documents = []
        posts = self.fetch_paginated(ENDPOINTS["posts"])

        for post in posts:
            post_docs = self._extract_post_media(post, "post")
            documents.extend(post_docs)

        logger.info(f"Found {len(documents)} document attachments in posts")
        return documents

    def _extract_news_attachments(self) -> List[DocumentInfo]:
        """Extract document attachments from news posts."""
        logger.info("Extracting document attachments from news posts...")

        documents = []
        news_posts = self.fetch_paginated(ENDPOINTS["news"])

        for post in news_posts:
            news_docs = self._extract_post_media(post, "news")
            documents.extend(news_docs)

        logger.info(f"Found {len(documents)} document attachments in news posts")
        return documents

    def _extract_post_media(self, post: Dict, post_type: str) -> List[DocumentInfo]:
        """Extract media from a single post."""
        documents = []

        # Check embedded media
        if "_embedded" not in post or "wp:featuredmedia" not in post["_embedded"]:
            return documents

        for media in post["_embedded"]["wp:featuredmedia"]:
            if not self._is_document_media(media):
                continue

            try:
                doc_info = self._create_media_document_info(media)
                # Add related post information
                doc_info.description = f"Attached to {post_type}: {post.get('title', {}).get('rendered', 'Unknown')}"
                documents.append(doc_info)
            except Exception as e:
                logger.warning(f"Failed to process media in {post_type} {post.get('id')}: {e}")

        return documents

    def _is_document_media(self, media_item: Dict) -> bool:
        """Check if media item is a document type we're interested in."""
        mime_type = media_item.get("mime_type", "")
        return ValidationUtils.is_document_type_supported(mime_type)

    def _create_media_document_info(self, media_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from WordPress media item."""
        title = media_item.get("title", {})
        if isinstance(title, dict):
            title = title.get("rendered", "Unknown")

        description = media_item.get("description", {})
        if isinstance(description, dict):
            description = description.get("rendered", "")

        caption = media_item.get("caption", {})
        if isinstance(caption, dict):
            caption = caption.get("rendered", "")

        return self._create_document_info(
            id_value=str(media_item["id"]),
            title=title,
            source_url=media_item["source_url"],
            mime_type=media_item.get("mime_type", ""),
            date=media_item["date"],
            modified=media_item.get("modified"),
            alt_text=media_item.get("alt_text", ""),
            description=description,
            caption=caption,
            file_size=media_item.get("media_details", {}).get("filesize", 0),
        )
