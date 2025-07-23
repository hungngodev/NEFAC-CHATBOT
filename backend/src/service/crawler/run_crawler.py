#!/usr/bin/env python3
"""
NEFAC Document Crawler - Main Entry Point

This is the single entry point for running the NEFAC document crawler.
Simple, clean interface that handles all the complex imports internally.
"""

import sys
from pathlib import Path

# Add the crawler directory to Python path
crawler_dir = Path(__file__).parent
sys.path.insert(0, str(crawler_dir))

from scripts.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
