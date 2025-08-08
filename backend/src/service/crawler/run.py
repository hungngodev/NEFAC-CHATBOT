#!/usr/bin/env python3
"""
Enhanced NEFAC Crawler - File Type Organization & Comprehensive Crawling

This script runs a comprehensive crawl with enhanced file-type organization:
1. ALL URLs from the WordPress sitemap (https://nefac.org/wp-sitemap.xml)
2. Complete NEFAC YouTube channel crawling with transcripts
3. WordPress REST API and GraphQL extraction
4. Intelligent deduplication and metadata merging
5. FILE-TYPE SPECIFIC ORGANIZATION (NEW):
   - youtube/ folder with videos + transcripts
   - html/ folder with web content
   - pdf/, docx/, xlsx/ folders by file type
   - images/, archives/ for media files

Usage:
    python run.py [options]
    
Examples:
    # Full comprehensive crawl with file-type organization (default)
    python run.py
    
    # Sitemap-only crawl (all sitemap URLs)
    python run.py --sitemap-only
    
    # YouTube-only crawl 
    python run.py --youtube-only
    
    # Custom output directory
    python run.py --output-dir /path/to/output
    
    # Enable debug logging
    python run.py --debug
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from collections import defaultdict

from src.service.crawler.core.main_crawler import NEFACCrawler
from src.service.crawler.core.config import CrawlerConfig

# Add backend directory to path for absolute imports
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))


def _analyze_documents(documents) -> tuple[dict, dict, dict]:
    """Analyze documents for file counts, content categories, and folder breakdown."""
    file_counts = defaultdict(int)
    content_categories = defaultdict(int)
    folder_breakdown = defaultdict(int)

    # Count files by extension and analyze folder organization
    for doc in documents:
        # File type analysis by extension
        if hasattr(doc, "file_extension") and doc.file_extension:
            ext = doc.file_extension.upper()
            file_counts[ext] += 1

        # Content category analysis
        if hasattr(doc, "metadata") and doc.metadata.get("content_category"):
            category = doc.metadata["content_category"]
            content_categories[category] += 1

        # Analyze which folder this would go to based on our new organization
        if hasattr(doc, "mime_type") and doc.mime_type:
            if "youtube" in doc.source.lower() or doc.mime_type == "video/youtube":
                folder_breakdown["youtube"] += 1
            elif "html" in doc.mime_type.lower():
                folder_breakdown["html"] += 1
            elif doc.mime_type == "application/pdf":
                folder_breakdown["pdf"] += 1
            elif "word" in doc.mime_type.lower() or "document" in doc.mime_type.lower():
                folder_breakdown["docx"] += 1
            elif (
                "excel" in doc.mime_type.lower()
                or "spreadsheet" in doc.mime_type.lower()
            ):
                folder_breakdown["xlsx"] += 1
            elif "image" in doc.mime_type.lower():
                folder_breakdown["images"] += 1
            else:
                folder_breakdown["other"] += 1

    return dict(file_counts), dict(content_categories), dict(folder_breakdown)


def _analyze_youtube_documents(documents) -> dict:
    """Analyze YouTube documents for folder breakdown."""
    folder_breakdown = defaultdict(int)
    for doc in documents:
        # Determine folder based on MIME type
        if "youtube" in doc.source.lower() or doc.mime_type == "video/youtube":
            folder_breakdown["youtube"] += 1
        elif doc.mime_type == "text/html":
            folder_breakdown["html"] += 1
        elif "pdf" in doc.mime_type:
            folder_breakdown["pdf"] += 1
        elif "word" in doc.mime_type or "document" in doc.mime_type:
            folder_breakdown["docx"] += 1
        elif "excel" in doc.mime_type or "spreadsheet" in doc.mime_type:
            folder_breakdown["xlsx"] += 1
        elif doc.mime_type.startswith("image/"):
            folder_breakdown["images"] += 1
        else:
            folder_breakdown["other"] += 1

    return dict(folder_breakdown)


def setup_logging(level: str = "INFO") -> None:
    """Configure comprehensive logging for the crawler."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    simple_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Console handler (simple format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)

    # File handler (detailed format)
    file_handler = logging.FileHandler("nefac_comprehensive_crawler.log")
    file_handler.setLevel(logging.DEBUG)  # Always debug in file
    file_handler.setFormatter(detailed_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("crawl4ai").setLevel(logging.INFO)


def print_banner():
    """Print NEFAC crawler banner."""
    print("=" * 80)
    print("    NEFAC OPTIMIZED CRAWLER v5.0 - MAXIMIZED DATA EXTRACTION")
    print("        New England First Amendment Coalition")
    print("=" * 80)
    print("  ⚡ MAXIMIZED SPEED: 200 concurrent requests, 0.05s delays")
    print("  📂 FILE-TYPE ORGANIZATION: youtube/, html/, pdf/, docx/, etc.")
    print("  🗺️  UNLIMITED SITEMAP: ALL URLs processed")
    print("  🎥 YOUTUBE AGGRESSIVE MODE: 5s delays, 2 concurrent requests")
    print("  📄 WordPress & GraphQL APIs at maximum speed")
    print("  🤖 AI-Powered Content Extraction (Crawl4AI)")
    print("  🔄 Intelligent Deduplication & Metadata Merging")
    print("")
    print("  🚀 Just run: python run.py (no arguments needed!)")
    print("=" * 80)
    print()


def run_comprehensive_crawl(config: CrawlerConfig) -> dict:
    """Run the comprehensive NEFAC crawl with enhanced file-type organization."""
    print("🚀 Starting COMPREHENSIVE NEFAC Crawl with FILE-TYPE ORGANIZATION...")
    print("📁 Files will be organized by type: youtube/, html/, pdf/, docx/, etc.")
    start_time = time.time()

    try:
        # Initialize crawler with enhanced configuration
        crawler = NEFACCrawler(config)

        # Run full comprehensive crawl with file-type organization
        documents = crawler.run_full_crawl()

        end_time = time.time()
        duration = end_time - start_time

        # Analyze the results for file breakdown by type
        file_counts, content_categories, folder_breakdown = _analyze_documents(
            documents
        )

        # Calculate statistics
        total_documents = len(documents)

        return {
            "success": True,
            "total_documents": total_documents,
            "duration_minutes": duration / 60,
            "documents_per_minute": (
                total_documents / (duration / 60) if duration > 0 else 0
            ),
            "file_counts": file_counts,
            "content_categories": content_categories,
            "folder_breakdown": folder_breakdown,
            "output_directory": str(config.output_dir),
        }

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Comprehensive crawl failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "total_documents": 0,
            "duration_minutes": 0,
        }


def run_sitemap_only_crawl(config: CrawlerConfig) -> dict:
    """Run sitemap-only crawl."""
    print("🗺️  Starting SITEMAP-ONLY crawl...")
    start_time = time.time()

    try:
        # Initialize crawler
        crawler = NEFACCrawler(config)

        # Run sitemap-only crawl
        documents = crawler.run_sitemap_only_crawl()

        end_time = time.time()
        duration = end_time - start_time

        # Analyze the results for file breakdown by type
        file_counts, content_categories, folder_breakdown = _analyze_documents(
            documents
        )

        # Calculate statistics
        total_documents = len(documents)

        return {
            "success": True,
            "total_documents": total_documents,
            "duration_minutes": duration / 60,
            "documents_per_minute": (
                total_documents / (duration / 60) if duration > 0 else 0
            ),
            "file_counts": file_counts,
            "content_categories": content_categories,
            "folder_breakdown": folder_breakdown,
            "output_directory": str(config.output_dir),
        }

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Sitemap-only crawl failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "total_documents": 0,
            "duration_minutes": 0,
        }


def run_youtube_only_crawl(config: CrawlerConfig) -> dict:
    """Run YouTube-only crawl."""
    print("🎥 Starting YOUTUBE-ONLY crawl...")
    logger = logging.getLogger(__name__)

    try:
        # Initialize crawler with enhanced configuration
        crawler = NEFACCrawler(config)

        # Run YouTube-only crawl
        documents = crawler.run_youtube_only_crawl()

        # Categorize documents by folder for reporting
        folder_breakdown = _analyze_youtube_documents(documents)

        return {
            "success": True,
            "mode": "youtube-only",
            "documents_count": len(documents),
            "folder_breakdown": folder_breakdown,
            "documents": documents,
        }

    except Exception as e:
        logger.exception("YouTube-only crawl failed")
        return {
            "success": False,
            "mode": "youtube-only",
            "error": str(e),
            "documents_count": 0,
        }


def print_results_summary(results: dict, mode: str):
    """Print results summary."""
    print("\n" + "=" * 80)
    print("📊 NEFAC CRAWLER RESULTS - SITEMAP-ONLY MODE - FILE-TYPE ORGANIZED")
    print("=" * 80)

    if results.get("success"):
        print("✅ Status: SUCCESS")
        print(f"📄 Total Documents: {results.get('total_documents', 0):,}")
        print(f"⏱️  Duration: {results.get('duration_minutes', 0):.1f} minutes")
        print(f"📁 Output: {results.get('output_directory', 'nefac_documents')}")

        # File type breakdown
        if results.get("folder_breakdown"):
            print("\n📂 File System Breakdown:")
            for folder, count in results["folder_breakdown"].items():
                print(f"  📊 {folder}/: {count} files")

        print("\n🎯 Key File-Type Organization Features:")
        print("   • YouTube videos with transcripts → youtube/ folder")
        print("   • Web pages and articles → html/ folder")
        print("   • PDF documents → pdf/ folder")
        print("   • Word documents → docx/ folder")
        print("   • Excel spreadsheets → xlsx/ folder")
        print("   • Images → images/ folder")
        print("   • Other files → other/ folder")
    else:
        print("❌ Status: FAILED")
        print(f"Error: {results.get('error', 'Unknown error')}")


def main():
    """Main entry point - Run comprehensive crawl by default."""
    parser = argparse.ArgumentParser(
        description="NEFAC Comprehensive Crawler - Extract ALL content from NEFAC website and YouTube channel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Optional mode overrides (comprehensive is default)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--sitemap-only",
        action="store_true",
        help="Crawl ONLY sitemap URLs (skip YouTube, skip APIs)",
    )
    mode_group.add_argument(
        "--youtube-only", action="store_true", help="Crawl ONLY YouTube channel"
    )
    mode_group.add_argument(
        "--no-youtube",
        action="store_true",
        help="Skip YouTube crawling (everything else at max speed)",
    )

    # Optional configuration overrides
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Override output directory (default: nefac_documents)",
    )
    parser.add_argument(
        "--max-urls", type=int, help="Limit URLs for testing (default: unlimited)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)

    # Print banner
    print_banner()

    # Load optimized configuration
    try:
        config = CrawlerConfig.from_env_file()
        print("✅ Using OPTIMIZED configuration for maximum speed")

        # Apply command line overrides if provided
        if args.output_dir:
            config.output_dir = Path(args.output_dir)
            print(f"📁 Output directory overridden: {config.output_dir}")

        if args.max_urls:
            # For testing - limit URLs but keep all other optimizations
            config.sitemap_max_total_urls = args.max_urls
            print(f"⚠️  Testing mode: Limited to {args.max_urls} URLs")

        # Ensure output directory exists
        config.output_dir.mkdir(parents=True, exist_ok=True)

        # Show optimized settings
        print(f"📁 Output directory: {config.output_dir}")
        print(f"🚀 Max concurrent requests: {config.max_concurrent_requests}")
        print(f"⚡ Request delay: {config.request_delay}s")
        print(f"👥 Max workers: {config.max_workers}")
        print(f"🎯 Crawl4AI batch size: {config.crawl4ai_batch_size}")

    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Determine mode and run appropriate crawl
    if args.youtube_only:
        print("🎥 Running YouTube-ONLY crawl...")
        mode = "youtube-only"
        results = run_youtube_only_crawl(config)
    elif args.sitemap_only:
        print("🗺️  Running Sitemap-ONLY crawl...")
        mode = "sitemap-only"
        results = run_sitemap_only_crawl(config)
    elif args.no_youtube:
        print("🚀 Running MAXIMUM SPEED crawl (no YouTube)...")
        # Temporarily disable YouTube for maximum speed using new config structure
        config.youtube.enabled = False
        config.enable_youtube_integration = False
        mode = "comprehensive-no-youtube"
        results = run_comprehensive_crawl(config)
    else:
        print("🏆 Running FULL COMPREHENSIVE crawl (optimized)...")
        mode = "comprehensive"
        results = run_comprehensive_crawl(config)

    # Print results
    print_results_summary(results, mode)

    # Exit with appropriate code
    sys.exit(0 if results.get("success", False) else 1)


if __name__ == "__main__":
    main()
