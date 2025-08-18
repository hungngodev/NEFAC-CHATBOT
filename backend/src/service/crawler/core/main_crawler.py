"""
Main crawler orchestrator for NEFAC documents.
"""

import logging
from typing import List

from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.core.types import (
    DocumentInfo,
    ExtendedDocumentInfo,
)
from src.service.crawler.core.discovery_engine import DiscoveryEngine
from src.service.crawler.downloaders.document_downloader import DocumentDownloader
from src.service.crawler.downloaders.metadata_manager import MetadataManager
from src.service.crawler.core.deduplication_consolidated import DeduplicationManager
from src.service.crawler.extractors.crawl4ai_extractor import Crawl4AIExtractor
from src.service.crawler.extractors.graphql_extractor import GraphQLExtractor
from src.service.crawler.extractors.wordpress_extractor import WordPressExtractor
from src.service.crawler.extractors.youtube_extractor import YouTubeExtractor
from src.service.crawler.extractors.comprehensive_file_extractor import (
    ComprehensiveFileExtractor,
)

logger = logging.getLogger(__name__)


class NEFACCrawler:
    """Main orchestrator for the NEFAC document crawler."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.crawl4ai_extractor = Crawl4AIExtractor(config)
        self.wordpress_extractor = WordPressExtractor(config)  # Use unified extractor
        self.graphql_extractor = GraphQLExtractor(config)
        self.youtube_extractor = YouTubeExtractor(config)
        self.file_extractor = ComprehensiveFileExtractor(config)
        self.downloader = DocumentDownloader(config)
        self.metadata_manager = MetadataManager(config)
        self.deduplication_manager = DeduplicationManager(config)
        self.discovery_engine = DiscoveryEngine(config)

    def crawl(self) -> List[DocumentInfo]:
        """Execute the full crawling pipeline."""
        logger.info("Starting NEFAC document crawling pipeline...")

        # Run all extractors
        logger.info("Starting WordPress REST API extraction...")
        wordpress_result = self.wordpress_extractor.extract()
        logger.info(
            f"WordPress extraction completed. Found {len(wordpress_result.documents)} documents."
        )

        logger.info("Starting GraphQL API extraction...")
        graphql_result = self.graphql_extractor.extract()
        logger.info(
            f"GraphQL extraction completed. Found {len(graphql_result.documents)} documents."
        )

        logger.info("Starting Crawl4AI extraction...")
        crawl4ai_result = self.crawl4ai_extractor.extract()
        logger.info(
            f"Crawl4AI extraction completed. Found {len(crawl4ai_result.documents)} documents."
        )

        # Check if YouTube is enabled in config
        youtube_documents = []
        if getattr(self.config, "enable_youtube_integration", True) and getattr(
            self.config.youtube, "enabled", True
        ):
            try:
                youtube_result = self.youtube_extractor.extract()
                youtube_documents = youtube_result.documents
                logger.info(
                    f"YouTube extraction completed. Found {len(youtube_documents)} videos."
                )
            except Exception as e:
                logger.error(f"YouTube extraction failed: {e}")
                youtube_documents = []
        else:
            logger.info("YouTube extraction skipped (disabled in config)")

        # Get comprehensive URL discovery for file extraction
        logger.info("Starting comprehensive URL discovery for file extraction...")
        url_entries = self.discovery_engine.get_comprehensive_url_discovery()

        # Run comprehensive file extractor
        file_extractor = ComprehensiveFileExtractor(self.config)
        file_result = file_extractor.extract(url_entries)

        # Convert file extraction results to DocumentInfo objects
        file_documents = []
        for doc_data in file_result.documents:
            if isinstance(doc_data, dict):
                # Create DocumentInfo from file extraction data
                doc_info = self._create_document_info_from_file_data(doc_data)
                if doc_info:
                    file_documents.append(doc_info)

        # Prepare documents by source for deduplication
        source_documents = {
            "wordpress_rest_api": wordpress_result.documents,
            "graphql_api": graphql_result.documents,
            "crawl4ai": crawl4ai_result.documents,
            "youtube": youtube_documents,
            "comprehensive_file_extractor": file_documents,
        }

        # Apply deduplication and metadata merging
        crawl_result = self.deduplication_manager.process_all_sources(source_documents)
        all_documents = crawl_result.documents

        logger.info(
            f"Deduplication results: {len(sum(source_documents.values(), []))} input documents → {len(all_documents)} unique documents"
        )
        logger.info(
            f"Duplicates found: {crawl_result.duplicates_found}, Duplicates merged: {crawl_result.duplicates_merged}"
        )

        # Convert ExtendedDocumentInfo to DocumentInfo for compatibility
        converted_documents = [
            self._convert_extended_to_document_info(doc) for doc in all_documents
        ]

        # Download HTML content for all documents
        html_documents = [
            doc for doc in converted_documents if doc.mime_type == "text/html"
        ]
        logger.info(f"Downloading HTML content for {len(html_documents)} documents...")

        downloaded_count = 0
        for doc in html_documents:
            try:
                # Download the HTML content
                if self.downloader.download(doc):
                    downloaded_count += 1
                else:
                    logger.warning(f"Failed to download HTML for {doc.source_url}")
            except Exception as e:
                logger.error(f"Failed to download HTML for {doc.source_url}: {e}")

        logger.info(
            f"HTML download completed. Successfully downloaded {downloaded_count}/{len(html_documents)} documents."
        )

        # Download non-HTML files using the downloader
        non_html_documents = [
            doc for doc in converted_documents if doc.mime_type != "text/html"
        ]
        logger.info(f"Downloading {len(non_html_documents)} non-HTML documents...")

        non_html_downloaded_count = 0
        for doc in non_html_documents:
            try:
                if self.downloader.download(doc):
                    non_html_downloaded_count += 1
                else:
                    logger.warning(
                        f"Failed to download {doc.mime_type} file from {doc.source_url}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to download {doc.mime_type} file from {doc.source_url}: {e}"
                )

        logger.info(
            f"Non-HTML download completed. Successfully downloaded {non_html_downloaded_count}/{len(non_html_documents)} documents."
        )

        # Save metadata for all documents
        logger.info(f"Saving metadata for {len(converted_documents)} documents...")
        try:
            self.metadata_manager.save_documents_metadata(converted_documents)
            logger.info("Metadata saving completed successfully.")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

        logger.info(
            f"Full crawl completed. Total documents: {len(converted_documents)}"
        )
        return converted_documents

    def run_full_crawl(self) -> List[DocumentInfo]:
        """Run the full comprehensive crawl with all extractors and downloaders."""
        return self.crawl()

    def run_sitemap_only_crawl(self) -> List[DocumentInfo]:
        """Run sitemap-only crawl using Crawl4AI extractor."""
        logger.info("Starting sitemap-only crawl...")

        # Run only the Crawl4AI extractor (sitemap parsing)
        crawl4ai_result = self.crawl4ai_extractor.extract()

        # Apply deduplication and metadata merging (even for single source)
        source_documents = {"crawl4ai": crawl4ai_result.documents}
        crawl_result = self.deduplication_manager.process_all_sources(source_documents)
        all_documents = crawl_result.documents

        logger.info(
            f"Deduplication results: {len(crawl4ai_result.documents)} input documents → {len(all_documents)} unique documents"
        )

        # Convert ExtendedDocumentInfo to DocumentInfo for compatibility
        converted_documents = [
            self._convert_extended_to_document_info(doc) for doc in all_documents
        ]

        # Download HTML content for all documents
        html_documents = [
            doc for doc in converted_documents if doc.mime_type == "text/html"
        ]
        logger.info(
            f"Downloading HTML content for {len(html_documents)} sitemap documents..."
        )

        downloaded_count = 0
        for doc in html_documents:
            try:
                # Download the HTML content
                if self.downloader.download(doc):
                    downloaded_count += 1
                else:
                    logger.warning(f"Failed to download HTML for {doc.source_url}")
            except Exception as e:
                logger.error(f"Failed to download HTML for {doc.source_url}: {e}")

        logger.info(
            f"HTML download completed. Successfully downloaded {downloaded_count}/{len(html_documents)} documents."
        )

        # Save metadata for all documents
        logger.info(f"Saving metadata for {len(converted_documents)} documents...")
        try:
            self.metadata_manager.save_documents_metadata(converted_documents)
            logger.info("Metadata saving completed successfully.")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

        logger.info(
            f"Sitemap-only crawl completed. Total documents: {len(converted_documents)}"
        )
        return converted_documents

    def run_youtube_only_crawl(self) -> List[DocumentInfo]:
        """Run YouTube-only crawl."""
        logger.info("Starting YouTube-only crawl...")
        youtube_result = self.youtube_extractor.extract()

        # Apply deduplication and metadata merging (even for single source)
        source_documents = {"youtube": youtube_result.documents}
        crawl_result = self.deduplication_manager.process_all_sources(source_documents)
        youtube_documents = crawl_result.documents

        logger.info(
            f"Deduplication results: {len(youtube_result.documents)} input documents → {len(youtube_documents)} unique documents"
        )

        # Convert ExtendedDocumentInfo to DocumentInfo for compatibility
        converted_documents = [
            self._convert_extended_to_document_info(doc) for doc in youtube_documents
        ]

        logger.info(
            f"YouTube-only crawl completed. Total documents: {len(converted_documents)}"
        )

        # Download YouTube content
        logger.info(f"Downloading {len(converted_documents)} YouTube videos...")

        downloaded_count = 0
        for doc in converted_documents:
            try:
                if self.downloader.download(doc):
                    downloaded_count += 1
                else:
                    logger.warning(
                        f"Failed to download YouTube video from {doc.source_url}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to download YouTube video from {doc.source_url}: {e}"
                )

        logger.info(
            f"YouTube download completed. Successfully downloaded {downloaded_count}/{len(converted_documents)} videos."
        )

        # Save metadata for YouTube documents
        logger.info(
            f"Saving metadata for {len(converted_documents)} YouTube documents..."
        )
        try:
            self.metadata_manager.save_documents_metadata(converted_documents)
            logger.info("YouTube metadata saving completed successfully.")
        except Exception as e:
            logger.error(f"Failed to save YouTube metadata: {e}")

        return converted_documents

    def run_comprehensive_crawl_no_youtube(self) -> List[DocumentInfo]:
        """Run comprehensive crawl without YouTube."""
        logger.info("Starting comprehensive crawl without YouTube...")

        # Run all extractors except YouTube
        wordpress_result = self.wordpress_extractor.extract()
        graphql_result = self.graphql_extractor.extract()
        crawl4ai_result = self.crawl4ai_extractor.extract()

        # Get comprehensive URL discovery for file extraction
        logger.info("Starting comprehensive URL discovery for file extraction...")
        url_entries = self.discovery_engine.get_comprehensive_url_discovery()

        # Run comprehensive file extractor
        file_extractor = ComprehensiveFileExtractor(self.config)
        file_result = file_extractor.extract(url_entries)

        # Convert file extraction results to DocumentInfo objects
        file_documents = []
        for doc_data in file_result.documents:
            if isinstance(doc_data, dict):
                # Create DocumentInfo from file extraction data
                doc_info = self._create_document_info_from_file_data(doc_data)
                if doc_info:
                    file_documents.append(doc_info)

        # Prepare documents by source for deduplication
        source_documents = {
            "wordpress_rest_api": wordpress_result.documents,
            "graphql_api": graphql_result.documents,
            "crawl4ai": crawl4ai_result.documents,
            "comprehensive_file_extractor": file_documents,
        }

        # Apply deduplication and metadata merging
        crawl_result = self.deduplication_manager.process_all_sources(source_documents)
        all_documents = crawl_result.documents

        logger.info(
            f"Deduplication results: {len(sum(source_documents.values(), []))} input documents → {len(all_documents)} unique documents"
        )
        logger.info(
            f"Duplicates found: {crawl_result.duplicates_found}, Duplicates merged: {crawl_result.duplicates_merged}"
        )

        # Convert ExtendedDocumentInfo to DocumentInfo for compatibility
        converted_documents = [
            self._convert_extended_to_document_info(doc) for doc in all_documents
        ]

        # Download HTML content for all documents
        html_documents = [
            doc for doc in converted_documents if doc.mime_type == "text/html"
        ]
        logger.info(f"Downloading HTML content for {len(html_documents)} documents...")

        downloaded_count = 0
        for doc in html_documents:
            try:
                # Download the HTML content
                if self.downloader.download(doc):
                    downloaded_count += 1
                else:
                    logger.warning(f"Failed to download HTML for {doc.source_url}")
            except Exception as e:
                logger.error(f"Failed to download HTML for {doc.source_url}: {e}")

        logger.info(
            f"HTML download completed. Successfully downloaded {downloaded_count}/{len(html_documents)} documents."
        )

        # Download non-HTML files using the downloader
        non_html_documents = [
            doc for doc in converted_documents if doc.mime_type != "text/html"
        ]
        logger.info(f"Downloading {len(non_html_documents)} non-HTML documents...")

        non_html_downloaded_count = 0
        for doc in non_html_documents:
            try:
                if self.downloader.download(doc):
                    non_html_downloaded_count += 1
                else:
                    logger.warning(
                        f"Failed to download {doc.mime_type} file from {doc.source_url}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to download {doc.mime_type} file from {doc.source_url}: {e}"
                )

        logger.info(
            f"Non-HTML download completed. Successfully downloaded {non_html_downloaded_count}/{len(non_html_documents)} documents."
        )

        # Save metadata for all documents
        logger.info(f"Saving metadata for {len(converted_documents)} documents...")
        try:
            self.metadata_manager.save_documents_metadata(converted_documents)
            logger.info("Metadata saving completed successfully.")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

        logger.info(
            f"Comprehensive crawl without YouTube completed. Total documents: {len(converted_documents)}"
        )
        return converted_documents

    def _convert_extended_to_document_info(
        self, extended_doc: ExtendedDocumentInfo
    ) -> DocumentInfo:
        """Convert ExtendedDocumentInfo to DocumentInfo for compatibility with existing components."""
        try:
            # Extract source information
            source = (
                extended_doc.sources[0].source_name
                if extended_doc.sources
                else "unknown"
            )
            source_url = extended_doc.url

            # Extract date information
            from datetime import datetime

            date = (
                extended_doc.published_date.isoformat()
                if extended_doc.published_date
                else datetime.now().isoformat()
            )
            modified = (
                extended_doc.modified_date.isoformat()
                if extended_doc.modified_date
                else None
            )

            # Extract file information
            download_date = (
                extended_doc.download_date.isoformat()
                if extended_doc.download_date
                else None
            )
            processing_timestamp = (
                extended_doc.download_date.timestamp()
                if extended_doc.download_date
                else None
            )

            # Create DocumentInfo object
            return DocumentInfo(
                id=extended_doc.id,
                title=extended_doc.title,
                source_url=source_url,
                mime_type=extended_doc.mime_type or "",
                date=date,
                modified=modified,
                source=source,
                file_size=extended_doc.file_size or 0,
                file_path=extended_doc.file_path,
                filename=extended_doc.filename,
                download_date=download_date,
                processing_timestamp=processing_timestamp,
                file_extension=extended_doc.file_extension,
                file_type_category=extended_doc.file_extension,  # Simplified mapping
            )
        except Exception as e:
            logger.error(f"Failed to convert ExtendedDocumentInfo to DocumentInfo: {e}")
            # Return a basic DocumentInfo as fallback
            return DocumentInfo(
                id=getattr(extended_doc, "id", "unknown"),
                title=getattr(extended_doc, "title", "Unknown Document"),
                source_url=getattr(extended_doc, "url", ""),
                mime_type=getattr(extended_doc, "mime_type", ""),
                date="",
                source="unknown",
            )

    def _create_document_info_from_file_data(self, file_data: dict) -> DocumentInfo:
        """Create DocumentInfo object from file extraction data."""
        try:
            # Extract relevant fields from file data
            url = file_data.get("url", "")
            title = file_data.get("title", "Untitled Document")
            mime_type = file_data.get("mime_type", "application/octet-stream")
            file_size = file_data.get("file_size", 0)

            # Create a basic DocumentInfo object
            from src.service.crawler.core.types import DocumentInfo
            import hashlib
            import time

            # Generate a unique ID based on URL
            doc_id = hashlib.md5(url.encode()).hexdigest()

            return DocumentInfo(
                id=doc_id,
                title=title,
                source_url=url,
                mime_type=mime_type,
                date=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                file_size=file_size,
                source="comprehensive_file_extractor",
            )
        except Exception as e:
            logger.error(f"Failed to create DocumentInfo from file data: {e}")
            return None
