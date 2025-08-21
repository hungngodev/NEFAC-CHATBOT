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

            # Log media document statistics
            media_mime_types = {}
            for doc in media_docs:
                mime_type = doc.mime_type if doc.mime_type else "unknown"
                media_mime_types[mime_type] = media_mime_types.get(mime_type, 0) + 1

            # Count specific document types
            word_media_docs = sum(
                1
                for doc in media_docs
                if doc.mime_type
                and (
                    "word" in doc.mime_type.lower()
                    or "document" in doc.mime_type.lower()
                )
            )
            pdf_media_docs = sum(
                1
                for doc in media_docs
                if doc.mime_type and "pdf" in doc.mime_type.lower()
            )
            excel_media_docs = sum(
                1
                for doc in media_docs
                if doc.mime_type
                and (
                    "excel" in doc.mime_type.lower()
                    or "spreadsheet" in doc.mime_type.lower()
                )
            )

            logger.info(
                f"Media documents extracted - Total: {len(media_docs)}, Word: {word_media_docs}, PDF: {pdf_media_docs}, Excel: {excel_media_docs}"
            )

            # Extract content with embedded documents
            content_docs = self._extract_content_documents()
            result.documents.extend(content_docs)

            # Extract news posts
            news_docs = self._extract_news_documents()
            result.documents.extend(news_docs)

            # Extract pages
            page_docs = self._extract_page_documents()
            result.documents.extend(page_docs)

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

                # Log sample node structure for debugging
                if nodes and len(nodes) > 0:
                    sample_node = nodes[0]
                    logger.debug(
                        f"Sample node keys: {list(sample_node.keys()) if sample_node else 'None'}"
                    )
                    if sample_node:
                        logger.debug(
                            f"Sample node sourceUrl: {sample_node.get('sourceUrl', 'MISSING')}"
                        )
                        if "mediaDetails" in sample_node:
                            media_details = sample_node.get("mediaDetails", {})
                            logger.debug(
                                f"Sample node mediaDetails keys: {list(media_details.keys()) if media_details else 'None'}"
                            )
                            if media_details:
                                logger.debug(
                                    f"Sample node mediaDetails file: {media_details.get('file', 'MISSING')}"
                                )

                # Log MIME type distribution for debugging
                mime_types = {}
                for node in nodes:
                    mime_type = node.get("mimeType", "unknown") if node else "unknown"
                    mime_types[mime_type] = mime_types.get(mime_type, 0) + 1

                # Log top MIME types
                sorted_mime_types = sorted(
                    mime_types.items(), key=lambda x: x[1], reverse=True
                )
                logger.debug(
                    f"MIME type distribution in this batch: {sorted_mime_types[:10]}"
                )

                # Count specific document types
                word_docs = sum(
                    1
                    for mt, count in mime_types.items()
                    if "word" in mt.lower() or "document" in mt.lower()
                )
                pdf_docs = sum(
                    1 for mt, count in mime_types.items() if "pdf" in mt.lower()
                )
                excel_docs = sum(
                    1
                    for mt, count in mime_types.items()
                    if "excel" in mt.lower() or "spreadsheet" in mt.lower()
                )
                logger.debug(
                    f"Document types in this batch - Word: {word_docs}, PDF: {pdf_docs}, Excel: {excel_docs}"
                )

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
                        uri
                        link
                        commentCount
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
                                databaseId
                                title
                                altText
                                sourceUrl
                                mediaDetails {
                                    width
                                    height
                                    file
                                    sizes {
                                        name
                                        sourceUrl
                                        width
                                        height
                                    }
                                }
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

            documents = self._fetch_paginated_content(
                "posts", query, self._create_content_document_info
            )
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

                JSONUtils.save_to_file(
                    content_metadata,
                    self.config.output_dir
                    / f"graphql_content_extraction_metadata_{int(time.time())}.json",
                )

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

        # If sourceUrl is empty, try to get it from mediaDetails
        if not source_url and media_item and "mediaDetails" in media_item:
            media_details = media_item.get("mediaDetails", {})
            if media_details and "file" in media_details:
                file_path = media_details.get("file", "")
                if file_path:
                    # Construct full URL from base URL and file path
                    from urllib.parse import urljoin

                    source_url = urljoin(
                        self.config.wordpress_base_url.rstrip("/") + "/",
                        file_path.lstrip("/"),
                    )
                    logger.debug(
                        f"Constructed source URL from mediaDetails: {source_url}"
                    )

        # If we still don't have a source URL, log this for debugging
        if not source_url:
            logger.warning(
                f"Document '{title}' (MIME: {mime_type}) has no source URL available"
            )

        # Log specific document types for debugging
        if mime_type and (
            "word" in mime_type.lower()
            or "document" in mime_type.lower()
            or (source_url and source_url.endswith(".docx"))
        ):
            logger.info(
                f"Processing Word document: {title} (ID: {media_id}, MIME: {mime_type}, URL: {source_url})"
            )
        elif mime_type and (
            "pdf" in mime_type.lower() or (source_url and source_url.endswith(".pdf"))
        ):
            logger.debug(
                f"Processing PDF document: {title} (ID: {media_id}, MIME: {mime_type})"
            )
        elif mime_type and (
            "excel" in mime_type.lower()
            or "spreadsheet" in mime_type.lower()
            or (source_url and source_url.endswith((".xls", ".xlsx")))
        ):
            logger.debug(
                f"Processing Excel document: {title} (ID: {media_id}, MIME: {mime_type})"
            )

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
        """Create DocumentInfo from GraphQL content item with enhanced URL handling and document extraction."""
        # Handle None content items
        if content_item is None:
            logger.warning("Received None content_item, skipping")
            return None

        # Use URI and link fields from GraphQL for accurate URLs
        base_url = self.config.wordpress_base_url
        uri = content_item.get("uri", "") if content_item else ""
        link = content_item.get("link", "") if content_item else ""
        slug = content_item.get("slug", "") if content_item else ""
        content_id = content_item.get("id", "unknown") if content_item else "unknown"
        
        # Prioritize link field, then construct from URI, then fallback to slug
        if link:
            source_url = link
        elif uri:
            source_url = f"{base_url.rstrip('/')}{uri}" if not uri.startswith('http') else uri
        elif slug:
            source_url = f"{base_url}/{slug}/"
        else:
            source_url = f"{base_url}/post/{content_id}"

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

        # Extract comment count
        comment_count = content_item.get("commentCount", 0) if content_item else 0

        # Extract enhanced featured image information
        featured_image_data = content_item.get("featuredImage", {}) if content_item else {}
        featured_image_node = featured_image_data.get("node", {}) if featured_image_data else {}
        featured_image_info = None
        
        if featured_image_node:
            media_details = featured_image_node.get("mediaDetails", {})
            featured_image_info = {
                "id": featured_image_node.get("id", ""),
                "databaseId": featured_image_node.get("databaseId", ""),
                "title": featured_image_node.get("title", ""),
                "altText": featured_image_node.get("altText", ""),
                "sourceUrl": featured_image_node.get("sourceUrl", ""),
                "width": media_details.get("width", 0) if media_details else 0,
                "height": media_details.get("height", 0) if media_details else 0,
                "file": media_details.get("file", "") if media_details else "",
                "sizes": media_details.get("sizes", []) if media_details else []
            }

        # Extract embedded document links from content
        content_text = content_item.get("content", "") if content_item else ""
        embedded_document_urls = []
        if content_text:
            embedded_document_urls = self._extract_document_links_from_html(content_text)
            
        # Save HTML content to file (from legacy comprehensive crawler functionality)
        try:
            content_metadata = self._save_post_content(content_item)
        except Exception as e:
            logger.warning(f"Failed to save post content for {content_id}: {e}")
            content_metadata = None

        # Create metadata dictionary with all the enhanced information
        metadata = {
            "comment_count": comment_count,
            "featured_image": featured_image_info,
            "embedded_document_urls": embedded_document_urls,
            "author": {
                "name": author_name,
                "slug": author_node.get("slug", "") if author_node else "",
                "uri": author_node.get("uri", "") if author_node else "",
                "description": author_node.get("description", "") if author_node else ""
            },
            "categories": category_names,
            "tags": tag_names,
            "content_metadata": content_metadata
        }

        # Get content for file size calculation  
        file_size = len(content_text.encode("utf-8")) if content_text else 0

        return self._create_document_info(
            id_value=content_id,
            title=content_item.get("title", "Untitled") if content_item else "Untitled",
            source_url=source_url,
            mime_type="text/html",
            date=content_item.get("date", "") if content_item else "",
            modified=content_item.get("modified", "") if content_item else "",
            description=description,
            file_size=file_size,
            metadata=metadata
        )

    def _extract_news_documents(self) -> List[DocumentInfo]:
        """Extract documents from news posts using GraphQL with enhanced error handling."""
        logger.info("Fetching news posts from GraphQL API...")

        try:
            query = """
            query GetNewsPosts($first: Int!, $after: String) {
                newsPosts(first: $first, after: $after) {
                    nodes {
                        id
                        databaseId
                        slug
                        title
                        date
                        modified
                        content
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

            documents = self._fetch_paginated_content(
                "newsPosts", query, self._create_news_document_info
            )
            logger.info(
                f"Successfully processed {len(documents)} news documents via GraphQL API"
            )

            # Save news metadata
            news_metadata = {
                "total_news_processed": len(documents),
                "extraction_timestamp": time.time(),
                "source": "graphql_news_extraction",
            }

            if news_metadata:
                from ..utils.common import JSONUtils

                JSONUtils.save_to_file(
                    news_metadata,
                    self.config.output_dir
                    / f"graphql_news_extraction_metadata_{int(time.time())}.json",
                )

            return documents

        except Exception as e:
            logger.error(f"Failed to extract news documents from GraphQL API: {e}")
            return []

    def _extract_page_documents(self) -> List[DocumentInfo]:
        """Extract documents from pages using GraphQL with enhanced error handling."""
        logger.info("Fetching pages from GraphQL API...")

        try:
            query = """
            query GetPages($first: Int!, $after: String) {
                pages(first: $first, after: $after) {
                    nodes {
                        id
                        databaseId
                        slug
                        title
                        date
                        modified
                        content
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

            documents = self._fetch_paginated_content(
                "pages", query, self._create_page_document_info
            )
            logger.info(
                f"Successfully processed {len(documents)} page documents via GraphQL API"
            )

            # Save page metadata
            page_metadata = {
                "total_pages_processed": len(documents),
                "extraction_timestamp": time.time(),
                "source": "graphql_page_extraction",
            }

            if page_metadata:
                from ..utils.common import JSONUtils

                JSONUtils.save_to_file(
                    page_metadata,
                    self.config.output_dir
                    / f"graphql_page_extraction_metadata_{int(time.time())}.json",
                )

            return documents

        except Exception as e:
            logger.error(f"Failed to extract page documents from GraphQL API: {e}")
            return []

    def _fetch_paginated_content(
        self, field_name: str, query: str, processor_func
    ) -> List[DocumentInfo]:
        """Fetch paginated content from GraphQL API."""
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
                    f"No data received from GraphQL API for {field_name}, breaking pagination loop"
                )
                break

            data = response["data"][field_name]
            nodes = data.get("nodes", [])
            logger.info(f"Retrieved {len(nodes)} {field_name} from GraphQL API")

            # Process nodes safely
            processed_docs = self._safe_process_items(nodes, processor_func, field_name)
            logger.info(
                f"Processed {len(processed_docs)} documents from {field_name} GraphQL API"
            )

            for doc_info in processed_docs:
                if items_fetched >= max_items:
                    break
                documents.append(doc_info)
                items_fetched += 1

            page_info = data.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                logger.info(
                    f"No more pages in GraphQL pagination for {field_name}, breaking loop"
                )
                break
            cursor = page_info.get("endCursor")
            time.sleep(self.config.request_delay)

        return documents

    def _create_news_document_info(self, content_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from GraphQL news item."""
        if not content_item:
            return None

        base_url = self.config.wordpress_base_url
        title = content_item.get("title", "")
        date_str = content_item.get("date", "")
        slug = content_item.get("slug", "")
        content_id = content_item.get("id", "unknown")
        source_url = f"{base_url}/{slug}/" if slug else f"{base_url}/news/{content_id}"

        # Get content for file size calculation
        content_text = content_item.get("content", "")
        file_size = len(content_text.encode("utf-8")) if content_text else 0

        # Get featured image ID
        featured_image_data = content_item.get("featuredImage", {})
        featured_image_node = (
            featured_image_data.get("node", {}) if featured_image_data else {}
        )
        featured_image_id = (
            featured_image_node.get("id", "") if featured_image_node else ""
        )

        # Extract embedded URLs from content
        embedded_urls = []
        if content_text:
            import re

            # Find all URLs in the content
            urls = re.findall(r'https?://[^\s"<>]+', content_text)
            embedded_urls = list(set(urls))  # Remove duplicates

        # Store content in metadata instead of passing as parameter
        metadata = {
            "featured_image_id": featured_image_id,
        }
        if embedded_urls:
            metadata["embedded_urls"] = embedded_urls

        return self._create_document_info(
            id_value=content_id,
            title=title,
            source_url=source_url,
            mime_type="text/html",
            date=date_str,
            file_size=file_size,
            metadata=metadata,
        )

    def _create_page_document_info(self, content_item: Dict) -> DocumentInfo:
        """Create DocumentInfo from GraphQL page item."""
        if not content_item:
            return None

        base_url = self.config.wordpress_base_url
        title = content_item.get("title", "")
        date_str = content_item.get("date", "")
        slug = content_item.get("slug", "")
        content_id = content_item.get("id", "unknown")
        source_url = f"{base_url}/{slug}/" if slug else f"{base_url}/page/{content_id}"

        # Get content for file size calculation
        content_text = content_item.get("content", "")
        file_size = len(content_text.encode("utf-8")) if content_text else 0

        # Get featured image ID
        featured_image_data = content_item.get("featuredImage", {})
        featured_image_node = (
            featured_image_data.get("node", {}) if featured_image_data else {}
        )
        featured_image_id = (
            featured_image_node.get("id", "") if featured_image_node else ""
        )

        # Extract embedded URLs from content
        embedded_urls = []
        if content_text:
            import re

            # Find all URLs in the content
            urls = re.findall(r'https?://[^\s"<>]+', content_text)
            embedded_urls = list(set(urls))  # Remove duplicates

        # Store content in metadata instead of passing as parameter
        metadata = {
            "featured_image_id": featured_image_id,
        }
        if embedded_urls:
            metadata["embedded_urls"] = embedded_urls

        return self._create_document_info(
            id_value=content_id,
            title=title,
            source_url=source_url,
            mime_type="text/html",
            date=date_str,
            file_size=file_size,
            metadata=metadata,
        )
