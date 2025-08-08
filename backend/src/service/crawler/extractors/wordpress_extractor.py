"""
WordPress REST API extractor for NEFAC documents.
"""

import logging
from typing import Dict, List

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import ENDPOINTS
from src.service.crawler.core.types import CrawlerSource, DocumentInfo, ExtractorResult
from src.service.crawler.utils.common import ValidationUtils
from src.service.crawler.extractors.base import (
    BaseExtractor,
    PaginationMixin,
    RequestMixin,
)

logger = logging.getLogger(__name__)


class WordPressExtractor(BaseExtractor, RequestMixin, PaginationMixin):
    """Extractor for WordPress REST API."""

    @property
    def source_name(self) -> str:
        return CrawlerSource.WORDPRESS_REST_API.value

    def extract(self) -> ExtractorResult:
        """Extract documents from WordPress REST API."""
        logger.info("Starting WordPress REST API extraction...")

        # Define extraction methods
        extraction_methods = [
            (self._extract_media_documents, "media"),
            (self._extract_post_attachments, "posts"),
            (self._extract_news_attachments, "news"),
        ]

        all_documents = []
        errors = []

        # Run all extraction methods
        for method, name in extraction_methods:
            try:
                documents = method()
                all_documents.extend(documents)
                logger.debug(f"Extracted {len(documents)} documents from {name}")
            except Exception as e:
                error_msg = f"WordPress {name} extraction failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(
            f"WordPress extraction complete. Found {len(all_documents)} documents."
        )
        return ExtractorResult(documents=all_documents, errors=errors)

    def _extract_media_documents(self) -> List[DocumentInfo]:
        """Extract document media items from WordPress REST API with enhanced error handling."""
        logger.info("Fetching media items from WordPress REST API...")

        try:
            # Use a much higher per_page limit to get ALL media
            media_endpoint = f"{ENDPOINTS['media']}?per_page=100"
            media_items = self.fetch_paginated(media_endpoint)
            logger.info(
                f"Retrieved {len(media_items)} total media items from WordPress API"
            )

            # Process ALL media items, not just documents - save everything as HTML files
            documents = []
            for item in media_items:
                try:
                    doc_info = self._create_media_document_info(item)
                    if doc_info:
                        documents.append(doc_info)
                except Exception as e:
                    logger.warning(
                        f"Failed to process media item {item.get('id', 'unknown')}: {e}"
                    )

            logger.info(
                f"Successfully processed {len(documents)} media documents via WordPress REST API"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to extract media documents from WordPress API: {e}")
            return []

    def _extract_post_attachments(self) -> List[DocumentInfo]:
        """Extract document attachments from posts with enhanced error handling."""
        logger.info("Extracting document attachments from posts...")

        try:
            # Get ALL posts with higher per_page limit and embedded media
            posts_endpoint = f"{ENDPOINTS['posts']}?per_page=100&_embed"
            posts = self.fetch_paginated(posts_endpoint)
            logger.info(f"Retrieved {len(posts)} posts from WordPress API")

            documents = []
            for post in posts:
                try:
                    # Create document for the post itself (as HTML)
                    post_doc = self._create_post_document_info(post, "post")
                    if post_doc:
                        documents.append(post_doc)

                    # Also extract any embedded media
                    post_media = self._extract_post_media(post, "post")
                    documents.extend(post_media)

                except Exception as e:
                    logger.warning(
                        f"Failed to process post {post.get('id', 'unknown')}: {e}"
                    )

            logger.info(f"Successfully processed {len(documents)} documents from posts")
            return documents

        except Exception as e:
            logger.error(f"Failed to extract post attachments from WordPress API: {e}")
            return []

    def _extract_news_attachments(self) -> List[DocumentInfo]:
        """Extract document attachments from news posts with enhanced error handling."""
        logger.info("Extracting document attachments from news posts...")

        try:
            # Get ALL news posts with higher per_page limit and embedded media
            news_endpoint = f"{ENDPOINTS['news']}?per_page=100&_embed"
            news_posts = self.fetch_paginated(news_endpoint)
            logger.info(f"Retrieved {len(news_posts)} news posts from WordPress API")

            documents = []
            for post in news_posts:
                try:
                    # Create document for the news post itself (as HTML)
                    news_doc = self._create_post_document_info(post, "news")
                    if news_doc:
                        documents.append(news_doc)

                    # Also extract any embedded media
                    post_media = self._extract_post_media(post, "news")
                    documents.extend(post_media)

                except Exception as e:
                    logger.warning(
                        f"Failed to process news post {post.get('id', 'unknown')}: {e}"
                    )

            logger.info(
                f"Successfully processed {len(documents)} documents from news posts"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to extract news attachments from WordPress API: {e}")
            return []

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
                logger.warning(
                    f"Failed to process media in {post_type} {post.get('id')}: {e}"
                )

        return documents

    def _is_document_media(self, media_item: Dict) -> bool:
        """Check if media item is a document type we're interested in."""
        mime_type = media_item.get("mime_type", "")
        return ValidationUtils.is_document_type_supported(mime_type)

    def _create_post_document_info(self, post: Dict, post_type: str) -> DocumentInfo:
        """Create DocumentInfo from WordPress post."""
        try:
            title = post.get("title", {})
            if isinstance(title, dict):
                title = title.get("rendered", "Unknown")

            content = post.get("content", {})
            if isinstance(content, dict):
                content = content.get("rendered", "")

            excerpt = post.get("excerpt", {})
            if isinstance(excerpt, dict):
                excerpt = excerpt.get("rendered", "")

            return self._create_document_info(
                id_value=str(post["id"]),
                title=title,
                source_url=post["link"],
                mime_type="text/html",
                date=post["date"],
                modified=post.get("modified"),
                description=excerpt,
                # content=content[:1000] if content else "",  # Preview of content - removed, not supported by DocumentInfo
                file_size=len(content.encode("utf-8")) if content else 0,
            )
        except Exception as e:
            logger.error(f"Failed to create document info from post: {e}")
            return None

    def _create_media_document_info(self, media_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from WordPress media item."""
        # Handle None media items
        if media_item is None:
            logger.warning("Received None media_item, skipping")
            return None

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
