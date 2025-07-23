#!/usr/bin/env python3
"""
Test script for the modular NEFAC crawler.

This script validates that all components work together correctly.
"""

import sys
from pathlib import Path

# Add the crawler directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.config import CrawlerConfig
    from core.main_crawler import NEFACCrawler
    from downloaders import DocumentDownloader, MetadataManager
    from extractors import GraphQLExtractor, WordPressExtractor

    print("✅ All imports successful!")

    # Test configuration
    config = CrawlerConfig(output_dir=Path("./test_output"), download_files=False, metadata_only=True)  # Don't download for test

    print("✅ Configuration created successfully!")

    # Test crawler initialization
    crawler = NEFACCrawler(config)
    print("✅ Crawler initialized successfully!")

    # Test extractor initialization
    wp_extractor = WordPressExtractor(config)
    print("✅ WordPress extractor initialized!")

    gql_extractor = GraphQLExtractor(config)
    print("✅ GraphQL extractor initialized!")

    # Test downloaders
    downloader = DocumentDownloader(config)
    print("✅ Document downloader initialized!")

    metadata_manager = MetadataManager(config)
    print("✅ Metadata manager initialized!")

    print("\n🎉 All components initialized successfully!")
    print("The modular NEFAC crawler is ready to use.")
    print("\nTo run the crawler:")
    print("  python cli.py --help")
    print("  python cli.py --metadata-only")
    print("  python cli.py --youtube-only")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the correct directory and have installed dependencies.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
