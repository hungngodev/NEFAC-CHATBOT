"""
GraphQL API extractor for NEFAC documents.
"""

import logging
import time
from typing import Dict, List, Optional

# Imports relative to the crawler directory (where run.py is located)
from src.service.crawler.core.config import ENDPOINTS
from src.service.crawler.core.types import CrawlerSource, DocumentInfo, ExtractorResult
from src.service.crawler.utils.common import (
    DateUtils,
    FileUtils,
    TextUtils,
)
from src.service.crawler.extractors.base import BaseExtractor, RequestMixin

logger = logging.getLogger(__name__)


class GraphQLExtractor(BaseExtractor, RequestMixin):
    """Extractor for GraphQL API."""

    @property
    def source_name(self) -> str:
        if self.config.faust_key:
            return CrawlerSource.GRAPHQL_AUTHENTICATED.value
        return CrawlerSource.GRAPHQL_API.value

    def extract(self) -> ExtractorResult:
        """Extract documents from GraphQL API."""
        self._log_start()
        result = ExtractorResult(documents=[])

        try:
            # Extract media documents
            media_docs = self._extract_media_documents()
            result.documents.extend(media_docs)

            # Extract content with embedded documents
            content_docs = self._extract_content_documents()
            result.documents.extend(content_docs)

        except Exception as e:
            error_msg = f"Error in GraphQL extraction: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        self._log_result(result)
        return result

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GraphQL requests."""
        headers = {"Content-Type": "application/json"}

        if self.config.faust_key:
            headers["Authorization"] = f"Bearer {self.config.faust_key}"
            logger.info("Using authenticated GraphQL requests")
        else:
            logger.info("Using public GraphQL requests")

        return headers

    def _make_graphql_request(
        self, query: str, variables: Optional[Dict] = None
    ) -> Dict:
        """Make a GraphQL request."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(
                ENDPOINTS["graphql"],
                json=payload,
                headers=self._get_headers(),
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.error(f"GraphQL errors: {result['errors']}")
                return {}

            return result
        except Exception as e:
            logger.error(f"GraphQL request failed: {e}")
            return {}

    def _extract_media_documents(self) -> List[DocumentInfo]:
        """Extract media documents using GraphQL with enhanced error handling."""
        logger.info("Fetching media documents from GraphQL API...")

        try:
            query = """
            query GetMediaItems($first: Int!, $after: String) {
                mediaItems(first: $first, after: $after) {
                    nodes {
                        id
                        databaseId
                        slug
                        title
                        date
                        modified
                        mediaType
                        mimeType
                        altText
                        caption
                        description
                        sourceUrl
                        mediaDetails {
                            file
                            height
                            width
                            sizes {
                                name
                                file
                                width
                                height
                                mimeType
                                sourceUrl
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """

            documents = []
            cursor = None
            items_fetched = 0
            max_items = self.config.max_items_per_source

            while items_fetched < max_items:
                variables = {
                    "first": min(self.config.per_page, max_items - items_fetched),
                    "after": cursor,
                }

                response = self._make_graphql_request(query, variables)
                if not response or "data" not in response:
                    logger.warning(
                        "No data received from GraphQL API, breaking pagination loop"
                    )
                    break

                media_data = response["data"]["mediaItems"]
                nodes = media_data.get("nodes", [])
                logger.info(f"Retrieved {len(nodes)} media nodes from GraphQL API")

                # Process nodes safely
                processed_docs = self._safe_process_items(
                    nodes, self._create_media_document_info, "media"
                )
                logger.info(
                    f"Processed {len(processed_docs)} media documents from GraphQL API"
                )

                for doc_info in processed_docs:
                    if items_fetched >= max_items:
                        break
                    documents.append(doc_info)
                    items_fetched += 1

                page_info = media_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    logger.info("No more pages in GraphQL pagination, breaking loop")
                    break
                cursor = page_info.get("endCursor")
                time.sleep(self.config.request_delay)

            logger.info(
                f"Successfully processed {len(documents)} media documents via GraphQL API"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to extract media documents from GraphQL API: {e}")
            return []

    def _extract_content_documents(self) -> List[DocumentInfo]:
        """Extract documents from post content using GraphQL with enhanced error handling."""
        logger.info("Fetching posts with content from GraphQL API...")

        try:
            query = """
            query GetPostsWithContent($first: Int!, $after: String) {
                posts(first: $first, after: $after) {
                    nodes {
                        id
                        databaseId
                        slug
                        title
                        date
                        modified
                        content
                        excerpt
                        author {
                            node {
                                name
                                slug
                                uri
                                description
                            }
                        }
                        categories {
                            nodes {
                                name
                                slug
                                description
                                count
                            }
                        }
                        tags {
                            nodes {
                                name
                                slug
                                description
                                count
                            }
                        }
                        featuredImage {
                            node {
                                id
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """

            documents = []
            cursor = None
            items_fetched = 0
            max_items = self.config.max_items_per_source

            while items_fetched < max_items:
                variables = {
                    "first": min(self.config.per_page, max_items - items_fetched),
                    "after": cursor,
                }

                response = self._make_graphql_request(query, variables)
                if not response or "data" not in response:
                    logger.warning(
                        "No data received from GraphQL API for content documents, breaking pagination loop"
                    )
                    break

                posts_data = response["data"]["posts"]
                nodes = posts_data.get("nodes", [])
                logger.info(f"Retrieved {len(nodes)} posts from GraphQL API")

                # Process nodes safely
                processed_docs = self._safe_process_items(
                    nodes, self._create_content_document_info, "content"
                )
                logger.info(
                    f"Processed {len(processed_docs)} content documents from GraphQL API"
                )

                for doc_info in processed_docs:
                    if items_fetched >= max_items:
                        break
                    documents.append(doc_info)
                    items_fetched += 1

                page_info = posts_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    logger.info(
                        "No more pages in GraphQL pagination for content documents, breaking loop"
                    )
                    break
                cursor = page_info.get("endCursor")
                time.sleep(self.config.request_delay)

            logger.info(
                f"Successfully processed {len(documents)} content documents via GraphQL API"
            )

            # Save content metadata
            content_metadata = {
                "total_posts_processed": len(documents),
                "extraction_timestamp": time.time(),
                "source": "graphql_content_extraction",
            }

            if content_metadata:
                from ..utils.common import JSONUtils

                # Ensure metadata directory exists
                metadata_dir = self.config.output_dir / "metadata"
                metadata_dir.mkdir(parents=True, exist_ok=True)

                metadata_file = metadata_dir / "content_metadata.json"
                JSONUtils.save_json(content_metadata, metadata_file)

            logger.info(f"Found {len(documents)} content documents from posts")
            return documents

        except Exception as e:
            logger.error(f"Failed to extract content documents from GraphQL API: {e}")
            return []

    def _save_post_content(self, post: Dict) -> Optional[Dict]:
        """Save post HTML content to file and return metadata."""
        try:
            post_id = post.get("databaseId", "unknown")
            title = post.get("title", "Untitled")
            content = post.get("content", "")

            # Clean up HTML content
            html_content = TextUtils.clean_html(content)

            if not html_content.strip():
                return None

            # Generate filename
            clean_title = FileUtils.generate_safe_filename(title)
            filename = f"post_{post_id}_{clean_title}.html"
            filepath = self.config.output_dir / "content" / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Save content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Create metadata
            author = post.get("author") or {}
            author_node = author.get("node", {})
            featured_image_data = post.get("featuredImage") or {}
            featured_image = featured_image_data.get("node", {})

            content_meta = {
                "id": post_id,
                "title": title,
                "slug": post.get("slug", ""),
                "url": post.get("link", ""),
                "uri": post.get("uri", ""),
                "date": post.get("date", ""),
                "modified": post.get("modified", ""),
                "excerpt": post.get("excerpt", ""),
                "content_length": len(html_content),
                "author": {
                    "name": author_node.get("name"),
                    "slug": author_node.get("slug"),
                    "uri": author_node.get("uri"),
                    "description": author_node.get("description"),
                },
                "categories": (post.get("categories") or {}).get("nodes", []),
                "tags": (post.get("tags") or {}).get("nodes", []),
                "featured_image": (
                    {
                        "id": featured_image.get("id"),
                        "title": featured_image.get("title"),
                        "alt_text": featured_image.get("altText"),
                        "source_url": featured_image.get("sourceUrl"),
                    }
                    if featured_image
                    else None
                ),
                "comment_count": 0,  # Field removed from GraphQL schema
                "mime_type": "text/html",
                "source": "graphql_content",
                "file_path": str(filepath),
                "file_size": filepath.stat().st_size,
                "download_date": DateUtils.get_current_iso_string(),
                "crawler_version": "3.0",
            }

            return content_meta

        except Exception as e:
            logger.error(f"Error saving post content: {e}")
            return None

    def _extract_embedded_documents(self, post: Dict) -> List[DocumentInfo]:
        """Extract document links from post content."""
        documents = []

        try:
            content = post.get("content", "")
            if not content:
                return documents

            # Extract document URLs from HTML content
            doc_links = self._extract_document_links_from_html(content)

            for link in doc_links:
                if link not in self.discovered_documents:
                    doc_info = self._create_document_info(
                        id_value=f"content-{post.get('databaseId')}-{FileUtils.get_filename_from_url(link)}",
                        title=FileUtils.extract_title_from_url(link),
                        source_url=link,
                        mime_type=FileUtils.guess_mime_type(link),
                        date=post.get("date", ""),
                        modified=post.get("modified", ""),
                        description=f"Extracted from post: {post.get('title', 'Unknown')}",
                    )
                    documents.append(doc_info)
                    self.discovered_documents.add(link)

        except Exception as e:
            logger.error(f"Error extracting embedded documents: {e}")

        return documents

    def _extract_document_links_from_html(self, html_content: str) -> List[str]:
        """Extract document URLs from HTML content."""
        import re
        from urllib.parse import urljoin

        # Look for PDF and document links
        document_patterns = [
            r'href=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']',
            r'src=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']',
        ]

        documents = []
        for pattern in document_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                if match.startswith("http"):
                    documents.append(match)
                else:
                    documents.append(urljoin(self.config.wordpress_base_url, match))

        return list(set(documents))  # Remove duplicates

    def _create_media_document_info(self, media_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from GraphQL media item."""
        # Handle None media items
        if media_item is None:
            logger.warning("Received None media_item, skipping")
            return None

        # Extract values safely
        media_id = media_item.get("id", "unknown") if media_item else "unknown"
        title = media_item.get("title", "Untitled") if media_item else "Untitled"
        source_url = media_item.get("sourceUrl", "") if media_item else ""
        mime_type = media_item.get("mimeType", "") if media_item else ""
        date = media_item.get("date", "") if media_item else ""
        modified = media_item.get("modified", "") if media_item else ""
        alt_text = media_item.get("altText", "") if media_item else ""
        description = media_item.get("description", "") if media_item else ""
        caption = media_item.get("caption", "") if media_item else ""

        return self._create_document_info(
            id_value=media_id,
            title=title,
            source_url=source_url,
            mime_type=mime_type,
            date=date,
            modified=modified,
            alt_text=alt_text,
            description=description,
            caption=caption,
            file_size=0,  # GraphQL doesn't provide file size
        )

    def _create_content_document_info(self, content_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from GraphQL content item."""
        # Handle None content items
        if content_item is None:
            logger.warning("Received None content_item, skipping")
            return None

        # Generate URL from base URL and slug
        base_url = self.config.wordpress_base_url
        slug = content_item.get("slug", "") if content_item else ""
        content_id = content_item.get("id", "unknown") if content_item else "unknown"
        source_url = f"{base_url}/{slug}/" if slug else f"{base_url}/post/{content_id}"

        # Extract categories and tags for description
        categories_data = content_item.get("categories", {}) if content_item else {}
        categories = categories_data.get("nodes", []) if categories_data else []
        tags_data = content_item.get("tags", {}) if content_item else {}
        tags = tags_data.get("nodes", []) if tags_data else []

        category_names = [cat.get("name", "") for cat in categories if cat is not None]
        tag_names = [tag.get("name", "") for tag in tags if tag is not None]

        # Build description from excerpt and metadata
        excerpt = content_item.get("excerpt", "") if content_item else ""
        description_parts = []
        if excerpt:
            # Clean HTML from excerpt
            import re

            clean_excerpt = re.sub(r"<[^>]+>", "", excerpt).strip()
            description_parts.append(clean_excerpt)

        if category_names:
            description_parts.append(f"Categories: {', '.join(category_names)}")
        if tag_names:
            description_parts.append(f"Tags: {', '.join(tag_names)}")

        description = " | ".join(description_parts)

        # Get author information
        author_data = content_item.get("author", {}) if content_item else {}
        author_node = author_data.get("node", {}) if author_data else {}
        author_name = author_node.get("name", "") if author_node else ""

        # Get content for file size calculation
        content_text = content_item.get("content", "") if content_item else ""
        file_size = len(content_text.encode("utf-8")) if content_text else 0

        # Get featured image ID
        featured_image_data = (
            content_item.get("featuredImage", {}) if content_item else {}
        )
        featured_image_node = (
            featured_image_data.get("node", {}) if featured_image_data else {}
        )
        featured_image_id = (
            featured_image_node.get("id") if featured_image_node else None
        )

        return self._create_document_info(
            id_value=content_id,
            title=content_item.get("title", "Untitled") if content_item else "Untitled",
            source_url=source_url,
            mime_type="text/html",
            date=content_item.get("date", "") if content_item else "",
            modified=content_item.get("modified", "") if content_item else "",
            description=description,
            file_size=file_size,
            metadata={
                "author": author_name,
                "categories": category_names,
                "tags": tag_names,
                "excerpt": excerpt,
                "slug": slug,
                "database_id": content_item.get("databaseId") if content_item else None,
                "featured_image_id": featured_image_id,
            },
        )
