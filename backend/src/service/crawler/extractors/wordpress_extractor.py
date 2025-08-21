"""
WordPress REST API extractor for NEFAC documents.
Direct API access using provided endpoint and secret key.
"""

import logging
import time
from typing import Dict, List, Optional
import requests
from urllib.parse import urljoin

from src.service.crawler.core.types import DocumentInfo, ExtractorResult
from src.service.crawler.extractors.base import BaseExtractor, RequestMixin
from src.service.crawler.utils.common import ValidationUtils

logger = logging.getLogger(__name__)


class WordPressExtractor(BaseExtractor, RequestMixin):
    """Enhanced extractor for WordPress REST API with optimized document retrieval."""

    # WordPress API configuration
    WORDPRESS_API_BASE = "https://nefac.org/wp-json/wp/v2/"
    SECRET_KEY = "faustt"  # Provided secret key

    def __init__(self, config):
        super().__init__(config)
        self.use_secret = True  # Flag to control secret usage
        self.request_delay = 0.5  # Delay between requests to be respectful

    @property
    def source_name(self) -> str:
        return "wordpress_rest_api"

    def extract(self) -> ExtractorResult:
        """Extract all documents from WordPress REST API directly."""
        logger.info("Starting WordPress REST API extraction...")

        all_documents = []
        errors = []
        warnings = []

        try:
            # First, test the API to determine optimal strategy
            self._test_api_access()

            # Extract all media items (documents)
            media_documents = self._extract_all_media()
            all_documents.extend(media_documents)

            logger.info(
                f"WordPress extraction complete. Found {len(all_documents)} documents."
            )

        except Exception as e:
            error_msg = f"WordPress extraction failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        return ExtractorResult(
            documents=all_documents, errors=errors, warnings=warnings
        )

    def _test_api_access(self) -> None:
        """Test API access to determine if secret provides additional access."""
        logger.info("Testing WordPress API access...")

        try:
            # Test without secret
            params_public = {"per_page": 1, "_fields": "id"}
            response_public = self.session.get(
                urljoin(self.WORDPRESS_API_BASE, "media"),
                params=params_public,
                timeout=10,
            )

            if response_public.status_code == 200:
                total_public = response_public.headers.get("x-wp-total", "0")
                logger.info(f"Public API access: {total_public} total items")
            else:
                logger.warning(
                    f"Public API access failed: {response_public.status_code}"
                )
                total_public = "0"

            # Test with secret
            if self.SECRET_KEY:
                params_auth = {
                    "per_page": 1,
                    "_fields": "id",
                    "secret": self.SECRET_KEY,
                }
                response_auth = self.session.get(
                    urljoin(self.WORDPRESS_API_BASE, "media"),
                    params=params_auth,
                    timeout=10,
                )

                if response_auth.status_code == 200:
                    total_auth = response_auth.headers.get("x-wp-total", "0")
                    logger.info(f"Authenticated API access: {total_auth} total items")

                    # Compare results
                    if int(total_auth) > int(total_public):
                        logger.info(
                            "Authentication provides access to additional items"
                        )
                        self.use_secret = True
                    elif int(total_auth) == int(total_public):
                        logger.info("Authentication provides same access as public API")
                        self.use_secret = False  # No benefit, avoid unnecessary auth
                    else:
                        logger.warning(
                            "Authentication provides fewer items than public API"
                        )
                        self.use_secret = False
                else:
                    logger.warning(
                        f"Authenticated API access failed: {response_auth.status_code}"
                    )
                    self.use_secret = False
            else:
                logger.info("No secret key provided, using public API only")
                self.use_secret = False

        except Exception as e:
            logger.warning(f"API test failed: {e}. Proceeding with default settings.")
            self.use_secret = True  # Default to using secret if test fails

    def _extract_all_media(self) -> List[DocumentInfo]:
        """Extract all media items from WordPress REST API with enhanced pagination."""
        logger.info("Fetching all media items from WordPress REST API...")

        try:
            # Test both with and without secret to see which gives more results
            all_media_items = []

            # Try with secret first
            if self.use_secret:
                logger.info("Attempting extraction with authentication...")
                media_with_secret = self._fetch_media_with_pagination(use_secret=True)
                logger.info(f"Found {len(media_with_secret)} items with authentication")
                all_media_items.extend(media_with_secret)

            # Also try without secret to compare/supplement
            logger.info("Attempting extraction without authentication...")
            media_without_secret = self._fetch_media_with_pagination(use_secret=False)
            logger.info(
                f"Found {len(media_without_secret)} items without authentication"
            )

            # Merge results, avoiding duplicates based on ID
            seen_ids = {item.get("id") for item in all_media_items}
            for item in media_without_secret:
                if item.get("id") not in seen_ids:
                    all_media_items.append(item)

            logger.info(f"Total unique media items: {len(all_media_items)}")

            # Filter for document types only
            document_items = [
                item
                for item in all_media_items
                if ValidationUtils.is_document_type_supported(item.get("mime_type", ""))
            ]

            logger.info(f"Filtered to {len(document_items)} document items")

            # Create DocumentInfo objects
            documents = []
            for item in document_items:
                try:
                    doc_info = self._create_media_document_info(item)
                    if doc_info:
                        documents.append(doc_info)
                except Exception as e:
                    logger.warning(
                        f"Failed to process media item {item.get('id', 'unknown')}: {e}"
                    )

            # Log document type breakdown
            self._log_document_breakdown(documents)

            logger.info(
                f"Successfully processed {len(documents)} documents via WordPress REST API"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to extract media from WordPress API: {e}")
            return []

    def _fetch_media_with_pagination(self, use_secret: bool = False) -> List[Dict]:
        """Fetch media items with proper pagination and error handling."""
        all_items = []
        page = 1
        max_pages = 500  # Safety limit to prevent infinite loops

        while page <= max_pages:
            try:
                # Build parameters properly
                params = {
                    "per_page": 100,
                    "page": page,
                    "_embed": True,  # Get embedded data for more complete info
                    "_fields": "id,title,source_url,mime_type,date,modified,description,caption,alt_text,media_details",
                }

                # Add secret if requested
                if use_secret and self.SECRET_KEY:
                    params["secret"] = self.SECRET_KEY

                # Make request with proper error handling
                url = urljoin(self.WORDPRESS_API_BASE, "media")
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                media_items = response.json()

                # Check for empty response (end of data)
                if not media_items or len(media_items) == 0:
                    logger.info(
                        f"No more items found at page {page}, stopping pagination"
                    )
                    break

                all_items.extend(media_items)

                # Log progress
                auth_status = "with auth" if use_secret else "without auth"
                logger.info(
                    f"Fetched page {page} {auth_status}: {len(media_items)} items (total: {len(all_items)})"
                )

                # Check if this was the last page (fewer items than requested)
                if len(media_items) < 100:
                    logger.info(
                        f"Last page reached (got {len(media_items)} < 100 items)"
                    )
                    break

                page += 1

                # Be respectful to the server
                if self.request_delay > 0:
                    time.sleep(self.request_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed on page {page}: {e}")
                # Try to continue with next page for transient errors
                if page == 1:
                    # If first page fails, give up
                    raise
                else:
                    # For later pages, log and continue
                    logger.warning(
                        f"Skipping page {page} due to request error, continuing..."
                    )
                    page += 1
                    continue

            except Exception as e:
                logger.error(f"Unexpected error on page {page}: {e}")
                break

        logger.info(
            f"Completed pagination: {len(all_items)} total items across {page-1} pages"
        )
        return all_items

    def _log_document_breakdown(self, documents: List[DocumentInfo]) -> None:
        """Log breakdown of document types found."""
        if not documents:
            logger.warning("No documents to analyze")
            return

        # Count by MIME type
        mime_counts = {}
        for doc in documents:
            mime_type = doc.mime_type.lower()
            mime_counts[mime_type] = mime_counts.get(mime_type, 0) + 1

        # Log specific categories
        pdf_count = mime_counts.get("application/pdf", 0)
        word_count = sum(count for mime, count in mime_counts.items() if "word" in mime)
        excel_count = sum(
            count
            for mime, count in mime_counts.items()
            if "excel" in mime or "spreadsheet" in mime
        )
        csv_count = mime_counts.get("text/csv", 0)
        txt_count = mime_counts.get("text/plain", 0)

        logger.info("Document breakdown:")
        logger.info(f"  - PDFs: {pdf_count}")
        logger.info(f"  - Word docs: {word_count}")
        logger.info(f"  - Excel docs: {excel_count}")
        logger.info(f"  - CSV files: {csv_count}")
        logger.info(f"  - Text files: {txt_count}")
        logger.info(
            f"  - Other types: {len(documents) - (pdf_count + word_count + excel_count + csv_count + txt_count)}"
        )

        # Log all MIME types found
        logger.info(f"All MIME types found: {sorted(mime_counts.keys())}")

    def _create_media_document_info(self, media_item: Dict) -> Optional[DocumentInfo]:
        """Create DocumentInfo from WordPress media item with enhanced error handling."""
        try:
            # Extract title with fallback
            title = media_item.get("title", {})
            if isinstance(title, dict):
                title = title.get("rendered", "")
            if not title or title.strip() == "":
                # Fallback to filename from source_url
                source_url = media_item.get("source_url", "")
                if source_url:
                    from urllib.parse import urlparse
                    import os

                    filename = os.path.basename(urlparse(source_url).path)
                    title = (
                        os.path.splitext(filename)[0]
                        if filename
                        else f"Document {media_item.get('id', 'Unknown')}"
                    )
                else:
                    title = f"Document {media_item.get('id', 'Unknown')}"

            # Extract description with fallback
            description = media_item.get("description", {})
            if isinstance(description, dict):
                description = description.get("rendered", "")

            # Extract caption with fallback
            caption = media_item.get("caption", {})
            if isinstance(caption, dict):
                caption = caption.get("rendered", "")

            # Validate required fields
            if not media_item.get("source_url"):
                logger.warning(
                    f"Media item {media_item.get('id')} has no source_url, skipping"
                )
                return None

            if not media_item.get("mime_type"):
                logger.warning(
                    f"Media item {media_item.get('id')} has no mime_type, skipping"
                )
                return None

            # Extract file size with better error handling
            file_size = 0
            media_details = media_item.get("media_details", {})
            if isinstance(media_details, dict):
                file_size = media_details.get("filesize", 0)
                # Sometimes filesize is a string
                if isinstance(file_size, str):
                    try:
                        file_size = int(file_size)
                    except (ValueError, TypeError):
                        file_size = 0

            return self._create_document_info(
                id_value=str(media_item["id"]),
                title=title.strip(),
                source_url=media_item["source_url"],
                mime_type=media_item.get("mime_type", ""),
                date=media_item.get("date", ""),
                modified=media_item.get("modified", ""),
                alt_text=media_item.get("alt_text", ""),
                description=description.strip() if description else "",
                caption=caption.strip() if caption else "",
                file_size=file_size,
            )
        except KeyError as e:
            logger.error(f"Missing required field in media item: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Failed to create document info from media item {media_item.get('id', 'unknown')}: {e}"
            )
            return None
