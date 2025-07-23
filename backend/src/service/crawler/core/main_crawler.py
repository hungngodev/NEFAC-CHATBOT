"""
Main crawler orchestrator for NEFAC document crawler.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..downloaders.document_downloader import DocumentDownloader
from ..downloaders.html_downloader import HTMLContentDownloader
from ..downloaders.metadata_manager import MetadataManager
from ..extractors.graphql_extractor import GraphQLExtractor
from ..extractors.link_discovery import LinkDiscoveryExtractor
from ..extractors.selenium_extractor import SeleniumExtractor
from ..extractors.web_scraper import WebScraperExtractor
from ..extractors.wordpress import WordPressExtractor
from ..extractors.youtube_extractor import YouTubeExtractor
from .config import CrawlerConfig
from .types import DocumentInfo

logger = logging.getLogger(__name__)


class NEFACCrawler:
    """Main crawler class that orchestrates all extraction and processing."""

    def __init__(self, config: CrawlerConfig):
        self.config = config

        # Initialize extractors
        self.wordpress_extractor = WordPressExtractor(config)
        self.graphql_extractor = GraphQLExtractor(config)
        self.web_scraper = WebScraperExtractor(config)
        self.youtube_extractor = YouTubeExtractor(config)
        self.selenium_extractor = SeleniumExtractor(config)
        self.link_discovery_extractor = LinkDiscoveryExtractor(config)

        # Initialize processors
        self.document_downloader = DocumentDownloader(config)
        self.metadata_manager = MetadataManager(config)
        self.html_downloader = HTMLContentDownloader(config)

        # Results storage
        self.all_documents: List[DocumentInfo] = []
        self.youtube_videos: List[Dict[str, Any]] = []
        self.web_content: List[Dict[str, Any]] = []

        # Statistics (matching original structure)
        self.stats = {
            "total_documents": 0,
            "downloaded_documents": 0,
            "failed_downloads": 0,
            "quarantined_documents": 0,
            "document_types": {},
            "sources": {
                "wordpress_rest_api": 0,
                "graphql_api": 0,
                "graphql_authenticated": 0,
                "web_scraping": 0,
                "link_discovery": 0,
                "content_extraction": 0,
                "selenium_scraper": 0,
                "youtube_channel": 0,
            },
            "start_time": datetime.now(),
            "end_time": None,
            "mime_types": {},
        }

        # Track discovered documents to avoid duplicates (like original)
        self.discovered_documents = set()

    def _update_document_stats(self, doc_info: DocumentInfo, source: str):
        """Update statistics for a document"""
        self.stats["total_documents"] += 1
        self.stats["sources"][source] += 1

        # Track document type
        if doc_info.file_extension:
            ext = doc_info.file_extension.lower()
            self.stats["document_types"][ext] = self.stats["document_types"].get(ext, 0) + 1

        # Track MIME type
        if doc_info.mime_type:
            mime = doc_info.mime_type
            self.stats["mime_types"][mime] = self.stats["mime_types"].get(mime, 0) + 1

    def _finalize_stats(self):
        """Finalize statistics"""
        self.stats["end_time"] = datetime.now()
        duration = self.stats["end_time"] - self.stats["start_time"]

        logger.info("CRAWLER STATISTICS:")
        logger.info(f"Total documents found: {self.stats['total_documents']}")
        logger.info(f"Documents downloaded: {self.stats['downloaded_documents']}")
        logger.info(f"Failed downloads: {self.stats['failed_downloads']}")
        logger.info(f"Quarantined documents: {self.stats['quarantined_documents']}")
        logger.info(f"Duration: {duration}")

        logger.info("Sources breakdown:")
        for source, count in self.stats["sources"].items():
            if count > 0:
                logger.info(f"  {source}: {count}")

        logger.info("Document types:")
        for doc_type, count in self.stats["document_types"].items():
            logger.info(f"  {doc_type}: {count}")

    def run_full_crawl(self) -> List[DocumentInfo]:
        """Run complete crawling process - matches original crawl() method."""
        logger.info("Starting comprehensive NEFAC document crawl...")

        try:
            # Phase 1: Document Extraction (matches original sequence)
            self._extract_documents()

            # Phase 2: Download Documents
            if self.config.download_files:
                self._download_documents()

            # Phase 3: Extract Non-Document Content
            self._extract_content()

            # Phase 4: Save Metadata
            self._save_metadata()

            # Phase 5: Generate Summary
            self._generate_summary()

            # Finalize statistics
            self._finalize_stats()

            logger.info("Full crawl completed successfully!")
            return self.all_documents

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            raise

    def run_youtube_only(self) -> List[Dict[str, Any]]:
        """Run YouTube-only crawl - matches original youtube_only mode."""
        logger.info("Starting YouTube-only crawl...")

        try:
            # Extract YouTube videos only
            youtube_result = self.youtube_extractor.extract()
            self.youtube_videos = youtube_result.metadata.get("youtube_videos", [])

            # Save YouTube metadata
            self.metadata_manager.save_youtube_metadata(self.youtube_videos)

            logger.info(f"YouTube-only crawl completed! Found {len(self.youtube_videos)} videos.")
            return self.youtube_videos

        except Exception as e:
            logger.error(f"YouTube crawl failed: {e}")
            raise

    def run_documents_only(self) -> List[DocumentInfo]:
        """Run crawl for documents only (PDFs, etc.)."""
        logger.info("Starting documents-only crawl...")

        self._extract_documents()
        if self.config.download_files:
            self._download_documents()
        self._save_document_metadata()

        logger.info("Documents-only crawl completed!")
        return self.all_documents

    def run_content_only(self) -> List[Dict[str, Any]]:
        """Run crawl for web content only."""
        logger.info("Starting content-only crawl...")

        self._extract_content()
        self._save_content_metadata()

        logger.info("Content-only crawl completed!")
        return self.youtube_videos + self.web_content

    def _extract_documents(self):
        """Extract document information from all sources."""
        logger.info("Extracting documents from all sources...")

        # WordPress documents
        try:
            wp_result = self.wordpress_extractor.extract()
            for doc in wp_result.documents:
                self._update_document_stats(doc, "wordpress_rest_api")
            self.all_documents.extend(wp_result.documents)
            logger.info(f"Extracted {len(wp_result.documents)} documents from WordPress")
        except Exception as e:
            logger.error(f"WordPress extraction failed: {e}")

        # GraphQL documents (with authentication)
        try:
            gql_result = self.graphql_extractor.extract()
            for doc in gql_result.documents:
                self._update_document_stats(doc, "graphql_authenticated")
            self.all_documents.extend(gql_result.documents)
            logger.info(f"Extracted {len(gql_result.documents)} documents from GraphQL")
        except Exception as e:
            logger.error(f"GraphQL extraction failed: {e}")

        # Web scraper documents
        try:
            web_result = self.web_scraper.extract()
            for doc in web_result.documents:
                self._update_document_stats(doc, "web_scraping")
            self.all_documents.extend(web_result.documents)
            logger.info(f"Extracted {len(web_result.documents)} documents from web scraper")
        except Exception as e:
            logger.error(f"Web scraper extraction failed: {e}")

        # Link discovery documents
        try:
            link_result = self.link_discovery_extractor.extract()
            for doc in link_result.documents:
                self._update_document_stats(doc, "link_discovery")
            self.all_documents.extend(link_result.documents)
            logger.info(f"Extracted {len(link_result.documents)} documents from link discovery")
        except Exception as e:
            logger.error(f"Link discovery extraction failed: {e}")

        # Remove duplicates based on source URL
        self._deduplicate_documents()

        logger.info(f"Total unique documents extracted: {len(self.all_documents)}")

    def _download_documents(self):
        """Download all extracted documents."""
        logger.info("Starting document downloads...")

        for doc_info in self.all_documents:
            try:
                success = self.document_downloader.download(doc_info)
                if success:
                    logger.debug(f"Downloaded: {doc_info.title}")
                else:
                    logger.warning(f"Failed to download: {doc_info.title}")
            except Exception as e:
                logger.error(f"Download error for {doc_info.title}: {e}")

        logger.info("Document downloads completed")

    def _extract_content(self):
        """Extract non-document content."""
        logger.info("Extracting web content and media...")

        # YouTube videos
        try:
            youtube_result = self.youtube_extractor.extract()
            self.youtube_videos = youtube_result.metadata.get("youtube_videos", [])
            # Update stats for YouTube content
            for video in self.youtube_videos:
                self.stats["sources"]["youtube_channel"] += 1
            logger.info(f"Extracted {len(self.youtube_videos)} YouTube videos")
        except Exception as e:
            logger.error(f"YouTube extraction failed: {e}")

        # Selenium-based content
        try:
            selenium_result = self.selenium_extractor.extract()
            selenium_content = selenium_result.metadata.get("selenium_content", [])
            # Update stats for Selenium content
            for content in selenium_content:
                self.stats["sources"]["selenium_scraper"] += 1
            self.web_content.extend(selenium_content)
            logger.info(f"Extracted {len(selenium_content)} items via Selenium")
        except Exception as e:
            logger.error(f"Selenium extraction failed: {e}")

        # HTML content from link discovery
        try:
            html_content = self.html_downloader.download_html_pages_from_links()
            # Update stats for HTML content
            for content in html_content:
                self.stats["sources"]["content_extraction"] += 1
            self.web_content.extend(html_content)
            logger.info(f"Downloaded {len(html_content)} HTML pages")
        except Exception as e:
            logger.error(f"HTML content download failed: {e}")

    def _save_metadata(self):
        """Save all metadata."""
        logger.info("Saving metadata...")

        self.metadata_manager.save_documents_metadata(self.all_documents)
        self.metadata_manager.save_youtube_metadata(self.youtube_videos)
        self.metadata_manager.save_images_metadata()

        logger.info("Metadata saved successfully")

    def _save_document_metadata(self):
        """Save document metadata only."""
        self.metadata_manager.save_documents_metadata(self.all_documents)

    def _save_content_metadata(self):
        """Save content metadata only."""
        self.metadata_manager.save_youtube_metadata(self.youtube_videos)
        self.metadata_manager.save_images_metadata()

    def _deduplicate_documents(self):
        """Remove duplicate documents based on source URL."""
        seen_urls = set()
        unique_documents = []

        for doc in self.all_documents:
            if doc.source_url not in seen_urls:
                seen_urls.add(doc.source_url)
                unique_documents.append(doc)
            else:
                logger.debug(f"Duplicate document removed: {doc.source_url}")

        original_count = len(self.all_documents)
        self.all_documents = unique_documents
        removed_count = original_count - len(unique_documents)

        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate documents")

    def _generate_summary(self):
        """Generate crawl summary report."""
        summary = {
            "total_documents": len(self.all_documents),
            "documents_by_type": self._count_by_type(),
            "youtube_videos": len(self.youtube_videos),
            "web_content_items": len(self.web_content),
            "output_directory": str(self.config.output_dir),
            "config": {
                "wordpress_url": self.config.wordpress_base_url,
                "max_workers": self.config.max_workers,
                "request_delay": self.config.request_delay,
            },
        }

        # Save summary
        summary_file = self.config.output_dir / "crawl_summary.json"
        from ..utils.common import JSONUtils

        JSONUtils.save_json(summary, summary_file)

        # Log summary
        logger.info("=== CRAWL SUMMARY ===")
        logger.info(f"Total documents: {summary['total_documents']}")
        logger.info(f"YouTube videos: {summary['youtube_videos']}")
        logger.info(f"Web content items: {summary['web_content_items']}")
        logger.info(f"Output directory: {summary['output_directory']}")

        for file_type, count in summary["documents_by_type"].items():
            logger.info(f"  {file_type}: {count}")

    def _count_by_type(self) -> Dict[str, int]:
        """Count documents by file type."""
        type_counts = {}

        for doc in self.all_documents:
            file_type = doc.file_extension or "unknown"
            type_counts[file_type] = type_counts.get(file_type, 0) + 1

        return type_counts

    def get_status(self) -> Dict[str, Any]:
        """Get current crawler status."""
        return {
            "documents_extracted": len(self.all_documents),
            "youtube_videos": len(self.youtube_videos),
            "web_content_items": len(self.web_content),
            "config": {
                "output_dir": str(self.config.output_dir),
                "wordpress_url": self.config.wordpress_base_url,
            },
        }
