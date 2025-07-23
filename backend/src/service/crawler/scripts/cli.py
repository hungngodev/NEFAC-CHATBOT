#!/usr/bin/env python3
"""
NEFAC Document Crawler - Command Line Interface

This is the modular version of the NEFAC document crawler.
Replaces the monolithic nefac-document-crawler.py script.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import CrawlerConfig
from core.main_crawler import NEFACCrawler


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    # Configure logging to match original
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler("nefac_crawler.log"), logging.StreamHandler()])


def main():
    """Main CLI entry point - matches original argument structure."""
    parser = argparse.ArgumentParser(
        description="NEFAC Document Crawler - Comprehensive document discovery and download tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run complete crawl with default settings
  %(prog)s --output-dir ./output     # Custom output directory
  %(prog)s --metadata-only           # Extract metadata without downloading files
  %(prog)s --youtube-only            # Extract only YouTube videos and transcripts
  %(prog)s --faust-key YOUR_KEY      # Use Faust key for enhanced GraphQL access
  %(prog)s --document-types pdf docx # Only extract specific document types
  %(prog)s --delay 2.0               # Set custom delay between YouTube requests
        """,
    )

    # Output configuration
    parser.add_argument("--output-dir", type=str, default="nefac_documents", help="Output directory for downloaded files (default: nefac_documents)")

    # Mode options
    parser.add_argument("--metadata-only", action="store_true", help="Extract metadata only without downloading files")
    parser.add_argument("--youtube-only", action="store_true", help="Extract only YouTube videos and transcripts")

    # Authentication
    parser.add_argument("--faust-key", type=str, help="Faust secret key for enhanced GraphQL access")
    parser.add_argument("--webshare-username", type=str, help="Webshare.io username for YouTube proxy access")
    parser.add_argument("--webshare-password", type=str, help="Webshare.io password for YouTube proxy access")

    # Filtering options
    parser.add_argument("--document-types", nargs="+", help="Document types to extract (e.g., pdf docx xlsx)")

    # Rate limiting
    parser.add_argument("--delay", type=float, default=10.0, help="Delay between YouTube requests in seconds (default: 10.0)")

    # Logging options
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress all output except errors")

    args = parser.parse_args()

    # Setup logging
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    try:
        # Get authentication from args or environment
        faust_key = args.faust_key or os.getenv("FAUST_SECRET_KEY")
        webshare_username = args.webshare_username or os.getenv("WEBSHARE_USERNAME")
        webshare_password = args.webshare_password or os.getenv("WEBSHARE_PASSWORD")

        # Create configuration
        config = CrawlerConfig(
            output_dir=Path(args.output_dir),
            download_files=not args.metadata_only,
            faust_key=faust_key,
            youtube_delay=args.delay,
            webshare_username=webshare_username,
            webshare_password=webshare_password,
        )

        # Set additional flags
        if args.metadata_only:
            config.metadata_only = True

        # Filter document types if specified
        if args.document_types:
            config.document_types = set(args.document_types)

        # Validate configuration
        config.validate()

        logger.info("Starting NEFAC Document Crawler (Modular Version)")
        logger.info(f"Output directory: {config.output_dir}")

        if faust_key:
            logger.info("✅ Using Faust secret key for enhanced GraphQL access")
        else:
            logger.info("⚠️  Using public APIs only (no Faust key provided)")

        # Initialize crawler
        crawler = NEFACCrawler(config)

        # Run appropriate crawl mode
        if args.youtube_only:
            logger.info("Running YouTube-only crawl...")
            youtube_documents = crawler.run_youtube_only()
            print(f"\nYouTube crawl completed! Found {len(youtube_documents)} videos.")
            print(f"Check the '{args.output_dir}/youtube' and '{args.output_dir}/metadata/youtube_metadata.json' for results.")
        else:
            logger.info("Running comprehensive crawl...")
            documents = crawler.run_full_crawl()
            print(f"\nComprehensive crawl completed! Found {len(documents)} documents.")
            if faust_key:
                print("✅ Used Faust secret key for enhanced GraphQL access")
            else:
                print("⚠️  Used public APIs only (no Faust key provided)")
            print(f"Check the '{args.output_dir}' directory for results.")

    except KeyboardInterrupt:
        logger.info("Crawl interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        if args.verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
