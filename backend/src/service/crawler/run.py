#!/usr/bin/env python3
"""Complete NEFAC Crawler - WordPress & YouTube Content Extraction"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import requests
from tqdm import tqdm

from src.schemas.metadata import BaseMetadata
from src.service.crawler.core.config import CrawlerConfig
from src.service.crawler.downloaders.document_downloader import DocumentDownloader
from src.service.crawler.downloaders.metadata_manager import MetadataManager
from src.service.crawler.downloaders.rigid_validator import RigidValidator
from src.service.crawler.extractors.wordpress_extractor import WordPressExtractor
from src.service.crawler.extractors.youtube_extractor import YouTubeExtractor

logger = logging.getLogger(__name__)


class CrawlStats:
    """Simple statistics tracker."""

    def __init__(self):
        self.wordpress = 0
        self.youtube = 0
        self.success = 0
        self.failed = 0
        self.errors = []
        self.start_time = time.time()

    @property
    def total_docs(self) -> int:
        return self.wordpress + self.youtube

    @property
    def duration(self) -> float:
        return time.time() - self.start_time

    def print_summary(self):
        print(f"\n✅ Complete: {self.total_docs} documents, {self.success} downloaded")
        print(f"⏱️  Duration: {self.duration/60:.1f}m")
        if self.failed:
            print(f"⚠️  Failed: {self.failed}")


class NEFACCrawler:
    """Complete NEFAC document crawler."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.stats = CrawlStats()
        self.max_workers = getattr(config, "max_workers", 5)

        # Initialize components
        self.downloader = DocumentDownloader(config)
        self.wordpress_extractor = WordPressExtractor(config, self.downloader)
        self.youtube_extractor = YouTubeExtractor(config)
        self.metadata_manager = MetadataManager(config)

    def extract_safe(self, extract_fn, source_name: str) -> List[BaseMetadata]:
        """Extract documents."""
        result = extract_fn()
        docs = result.documents if result else []
        logger.info(f"📊 {source_name}: {len(docs)} documents")
        return docs

    def download_safe(self, doc: BaseMetadata) -> bool:
        """Safely download a single document."""
        try:
            self.downloader.download(doc)
            return True
        except Exception:
            return False

    def download_parallel(self, documents: List[BaseMetadata]):
        """Download documents in parallel with progress bar."""
        if not documents:
            return

        logger.info(f"📥 Downloading {len(documents)} documents...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_doc = {executor.submit(self.download_safe, doc): doc for doc in documents}

            # Process with progress bar
            with tqdm(total=len(documents), desc="Downloading", unit="docs", ncols=80, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:

                for future in as_completed(future_to_doc):
                    try:
                        if future.result():
                            self.stats.success += 1
                        else:
                            self.stats.failed += 1
                    except Exception as e:
                        self.stats.failed += 1
                        self.stats.errors.append(f"Download error: {e}")

                    pbar.set_postfix({"✅": self.stats.success, "❌": self.stats.failed})
                    pbar.update(1)

    def crawl(self, mode: str = "full", validate_sync: bool = True, incremental: bool = False) -> List[BaseMetadata]:
        """Main crawl orchestrator with comprehensive validation."""
        logger.info(f"🚀 Starting {mode} crawl (Incremental: {incremental})...")

        # Get incremental state if needed
        after_date = None
        ignore_ids = None
        if incremental:
            after_date, ignore_ids = self.metadata_manager.get_crawl_state()
            if after_date:
                logger.info(f"📅 Incremental: WordPress after {after_date}")
            if ignore_ids:
                logger.info(f"🎥 Incremental: Skipping {len(ignore_ids)} YouTube videos")

        # Extract documents based on mode
        wordpress_docs = []
        youtube_docs = []

        if mode in ["full", "wordpress"]:
            # Pass after_date to WordPress extractor
            wordpress_docs = self.extract_safe(lambda: self.wordpress_extractor.extract(after_date=after_date), "WordPress")
            self.stats.wordpress = len(wordpress_docs)

        if mode in ["full", "youtube"] and self.config.enable_youtube_integration:
            # Pass ignore_ids to YouTube extractor
            youtube_docs = self.extract_safe(lambda: self.youtube_extractor.extract(ignore_ids=ignore_ids), "YouTube")
            self.stats.youtube = len(youtube_docs)

        all_docs = wordpress_docs + youtube_docs
        logger.info(f"📄 Processing {len(all_docs)} unique documents")

        # Download and save
        self.download_parallel(all_docs)
        self.metadata_manager.save_documents_metadata(all_docs)

        # Rigid validation (zero tolerance)
        if validate_sync:
            validator = RigidValidator(self.config)
            result = validator.validate(fix_issues=True)

            if result.has_critical_issues:
                self.metadata_manager.save_documents_metadata(all_docs)
                raise RuntimeError("Critical synchronization failures - zero tolerance violated")
            elif result.has_any_issues:
                self.metadata_manager.save_documents_metadata(all_docs)
                logger.warning("Non-critical issues detected and fixed")
            else:
                logger.info("✅ Perfect synchronization achieved")

        self.stats.print_summary()
        return all_docs


def setup_logging(debug: bool = False, quiet: bool = False) -> None:
    """Setup logging configuration."""
    if quiet:
        level = logging.WARNING
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", datefmt="%H:%M:%S")


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="NEFAC Crawler")

    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--youtube-only", action="store_true", help="Crawl only YouTube content")
    mode.add_argument("--wordpress-only", "--no-youtube", action="store_true", help="Crawl only WordPress content (skip YouTube)")
    mode.add_argument("--sync-only", action="store_true", help="Only run synchronization validation (no crawling)")

    # Options
    parser.add_argument("--incremental", action="store_true", help="Incremental crawl (only new content)")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    # Validation options
    parser.add_argument("--no-validation", action="store_true", help="Skip synchronization validation after crawling")
    parser.add_argument("--fix-issues", action="store_true", help="Automatically fix synchronization issues")

    return parser


def _run_pre_flight_check(config: CrawlerConfig) -> bool:
    """Quick pre-flight check."""
    try:
        # Check output directory
        config.output_dir.mkdir(parents=True, exist_ok=True)
        test_file = config.output_dir / "test.tmp"
        test_file.write_text("test")
        test_file.unlink()

        # Check network
        requests.get("https://nefac.org", timeout=10)
        return True
    except Exception as e:
        print(f"Pre-flight check failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    setup_logging(args.debug, args.quiet)

    try:
        # Setup configuration
        config = CrawlerConfig.from_env_file()
        config.max_workers = args.workers

        if args.output_dir:
            config.output_dir = Path(args.output_dir)
            config.output_dir.mkdir(parents=True, exist_ok=True)

        # Pre-flight check
        if not _run_pre_flight_check(config):
            print("❌ Pre-flight checks failed")
            sys.exit(1)

        # Initialize crawler
        crawler = NEFACCrawler(config)

        # Sync-only mode
        if args.sync_only:
            validator = RigidValidator(config)
            result = validator.validate(fix_issues=args.fix_issues)
            sys.exit(2 if result.has_critical_issues else 1 if result.has_any_issues else 0)

        # Determine crawl mode
        if args.youtube_only:
            mode = "youtube"
        elif args.wordpress_only:  # This catches both --wordpress-only and --no-youtube
            mode = "wordpress"
        else:
            mode = "full"

        # Run crawl
        print(f"🚀 NEFAC Crawler - {mode.title()} Mode")
        print(f"📁 Output: {config.output_dir}")
        print(f"👥 Workers: {args.workers}")
        print(f"🔍 Validation: {'Disabled' if args.no_validation else 'Enabled'}")

        validate_sync = not args.no_validation

        is_incremental = getattr(args, "incremental", False)

        documents = crawler.crawl(mode, validate_sync=validate_sync, incremental=is_incremental)

        print(f"🎉 Done: {len(documents)} documents processed")

    except KeyboardInterrupt:
        print("\n⏹️ Interrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()
