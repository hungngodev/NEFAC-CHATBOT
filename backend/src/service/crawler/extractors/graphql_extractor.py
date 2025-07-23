"""
GraphQL API extractor for NEFAC documents.
"""

import logging
import time
from typing import Dict, List, Optional

from ..core.config import ENDPOINTS
from ..core.types import CrawlerSource, DocumentInfo, ExtractorResult
from ..utils.common import DateUtils, FileUtils, TextUtils, ValidationUtils
from .base import BaseExtractor, RequestMixin

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
        self._log_extraction_start()

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

        self._log_extraction_result(result)
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

    def _make_graphql_request(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Make a GraphQL request."""
        payload = {"query": query, "variables": variables or {}}

        try:
            response = self.get_session().post(ENDPOINTS["graphql"], json=payload, headers=self._get_headers(), timeout=self.config.request_timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GraphQL request failed: {e}")
            return None

    def _extract_media_documents(self) -> List[DocumentInfo]:
        """Extract media documents using GraphQL."""
        logger.info("Fetching media items from GraphQL API...")

        query = """
        query GetMediaItems($first: Int!, $after: String) {
            mediaItems(first: $first, after: $after) {
                nodes {
                    id
                    title
                    sourceUrl
                    mimeType
                    date
                    modified
                    altText
                    description
                    caption
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """

        documents = []
        has_next_page = True
        after_cursor = None

        while has_next_page:
            variables = {"first": 100, "after": after_cursor}

            response_data = self._make_graphql_request(query, variables)
            if not response_data or "data" not in response_data:
                break

            if "errors" in response_data:
                logger.error(f"GraphQL errors: {response_data['errors']}")
                break

            data = response_data["data"]["mediaItems"]
            media_items = data["nodes"]
            page_info = data["pageInfo"]

            for item in media_items:
                if not ValidationUtils.is_document_type_supported(item.get("mimeType", "")):
                    continue

                try:
                    doc_info = self._create_media_document_info(item)
                    documents.append(doc_info)
                except Exception as e:
                    logger.warning(f"Failed to process GraphQL media item {item.get('id')}: {e}")

            has_next_page = page_info["hasNextPage"]
            after_cursor = page_info["endCursor"]

            logger.debug(f"Fetched {len(media_items)} items from GraphQL API")
            time.sleep(self.config.request_delay)

        logger.info(f"Found {len(documents)} media documents via GraphQL API")
        return documents

    def _extract_content_documents(self) -> List[DocumentInfo]:
        """Extract documents from post content using GraphQL."""
        logger.info("Fetching posts with content from GraphQL API...")

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
                    uri
                    link
                    commentCount
                    featuredImage {
                        node {
                            id
                            databaseId
                            title
                            altText
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
        content_metadata = []
        has_next_page = True
        after_cursor = None

        while has_next_page:
            variables = {"first": 100, "after": after_cursor}

            response_data = self._make_graphql_request(query, variables)
            if not response_data or "data" not in response_data:
                break

            data = response_data["data"]["posts"]
            posts = data.get("nodes", [])
            page_info = data.get("pageInfo", {})

            for post in posts:
                try:
                    # Save HTML content
                    content_doc = self._save_post_content(post)
                    if content_doc:
                        content_metadata.append(content_doc)

                    # Extract embedded document links
                    embedded_docs = self._extract_embedded_documents(post)
                    documents.extend(embedded_docs)

                except Exception as e:
                    logger.error(f"Error processing post {post.get('databaseId')}: {e}")

            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")

            logger.debug(f"Processed {len(posts)} posts from GraphQL API")

        # Save content metadata
        if content_metadata:
            from ..utils.common import JSONUtils

            metadata_file = self.config.output_dir / "metadata" / "content_metadata.json"
            JSONUtils.save_json(content_metadata, metadata_file)

        logger.info(f"Found {len(documents)} embedded documents from posts")
        return documents

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
            author_node = post.get("author", {}).get("node", {})
            featured_image = post.get("featuredImage", {}).get("node", {})

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
                "categories": post.get("categories", {}).get("nodes", []),
                "tags": post.get("tags", {}).get("nodes", []),
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
                "comment_count": post.get("commentCount", 0),
                "mime_type": "text/html",
                "source": "graphql_content",
                "file_path": str(filepath),
                "file_size": filepath.stat().st_size,
                "download_date": DateUtils.now_iso(),
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
        return self._create_document_info(
            id_value=media_item["id"],
            title=media_item["title"],
            source_url=media_item["sourceUrl"],
            mime_type=media_item.get("mimeType", ""),
            date=media_item["date"],
            modified=media_item.get("modified"),
            alt_text=media_item.get("altText", ""),
            description=media_item.get("description", ""),
            caption=media_item.get("caption", ""),
            file_size=0,  # GraphQL doesn't provide file size
        )
