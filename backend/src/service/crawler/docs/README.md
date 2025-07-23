# NEFAC Document Crawler - Modular Version

This directory contains the refactored, modular version of the NEFAC document crawler that replaces the monolithic `nefac-document-crawler.py` (2241 lines).

## Overview

The crawler has been completely refactored into a clean, modular architecture with separated concerns while maintaining **100% compatibility** with the original functionality.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy configuration template
cp .env.example .env

# 3. Edit .env with your Faust key and other settings
nano .env

# 4. Run the crawler
python cli.py

# Alternative: YouTube-only mode
python cli.py --youtube-only

# Alternative: Metadata-only mode
python cli.py --metadata-only
```

## Architecture

```
crawler/
├── cli.py                     # Command-line interface (replaces original script)
├── main_crawler.py            # Main orchestrator class
├── config.py                  # Configuration management
├── types.py                   # Type definitions and dataclasses
├── __init__.py               # Package initialization
├── extractors/               # Modular data source extractors
│   ├── __init__.py
│   ├── base.py              # Base extractor with mixins
│   ├── wordpress.py         # WordPress REST API extractor
│   ├── graphql_extractor.py # GraphQL API extractor (Faust auth)
│   ├── web_scraper.py       # Link scraper integration
│   ├── youtube_extractor.py # YouTube content extractor (with proxy)
│   └── selenium_extractor.py # Selenium-based dynamic scraper
├── downloaders/              # File processing and metadata
│   ├── __init__.py
│   ├── document_downloader.py # File download and validation
│   └── metadata_manager.py   # Metadata saving with schema validation
├── utils/                    # Common utilities
│   ├── __init__.py
│   └── common.py            # JSON, date, and logging utilities
├── requirements.txt          # Python dependencies
├── .env.example             # Configuration template
└── README.md               # This file
```

## Key Improvements

1. **Separation of Concerns**: Each extractor handles one data source
2. **Reusable Components**: Base classes with mixins for common functionality
3. **Better Error Handling**: Granular error handling per component
4. **Configuration Management**: Centralized config with environment variables
5. **Extensibility**: Easy to add new extractors or modify existing ones
6. **Maintainability**: Clear structure with single responsibility principle
7. **Type Safety**: Full type hints and dataclasses

## Usage Examples

### Command Line Interface

The new CLI provides the same functionality as the original script:

```bash
# Full crawl (replaces original python nefac-document-crawler.py)
python cli.py

# YouTube-only crawl
python cli.py --youtube-only

# Metadata-only (no file downloads)
python cli.py --metadata-only

# Custom output directory
python cli.py --output-dir ./custom_output

# Specific document types
python cli.py --document-types pdf docx

# With authentication
python cli.py --faust-key YOUR_FAUST_KEY

# With YouTube proxy
python cli.py --webshare-username USER --webshare-password PASS

# Verbose logging
python cli.py --verbose
```

### Programmatic Usage

```python
from crawler import NEFACCrawler, CrawlerConfig

# Load configuration from .env file
config = CrawlerConfig.from_env_file('.env')

# Or create configuration manually
config = CrawlerConfig(
    output_dir=Path('./output'),
    faust_key='your_faust_key',
    download_files=True
)

# Initialize crawler
crawler = NEFACCrawler(config)

# Run different types of crawls
documents = crawler.run_full_crawl()         # Complete crawl
documents = crawler.run_documents_only()     # Documents only
videos = crawler.run_youtube_only()          # YouTube only
content = crawler.run_content_only()         # Web content only
```

## Preserved Functionality

The modular version maintains **100% compatibility** with the original:

### ✅ All Extraction Methods

- WordPress REST API integration with pagination
- GraphQL API with Faust authentication for enhanced access
- Link scraper tool integration
- Selenium scraper integration for dynamic content
- YouTube video extraction with transcript API
- Web scraping for additional document discovery

### ✅ File Processing

- PDF validation and quarantine system
- File organization by year/type
- Comprehensive metadata generation
- HTTP header preservation
- File type categorization

### ✅ Advanced Features

- Webshare proxy support for YouTube transcripts
- YouTube-only mode
- Metadata-only mode
- Document type filtering
- Rate limiting and retry logic
- Comprehensive logging and statistics

### ✅ Output Compatibility

- Same directory structure: `documents/`, `metadata/`, `content/`, `quarantine/`, `images/`, `youtube/`
- Same metadata schemas: `PDFMetadata`, `ContentMetadata`, `YouTubeMetadata`
- Same JSON output format
- Same crawl summary structure

## Configuration

The crawler uses environment variables for configuration:

```bash
# Required
FAUST_SECRET_KEY=your_faust_secret_key

# Optional
OUTPUT_DIR=nefac_documents
WORDPRESS_BASE_URL=https://nefac.org
WEBSHARE_USERNAME=your_username
WEBSHARE_PASSWORD=your_password
YOUTUBE_DELAY=10.0
MAX_WORKERS=5
```

## Migration from Original

Simply replace your existing usage:

```bash
# Old way
python nefac-document-crawler.py --metadata-only

# New way
python cli.py --metadata-only
```

All command-line arguments and functionality are preserved.

## Benefits

1. **Readability**: 2241 lines → modular components
2. **Maintainability**: Changes to one extractor don't affect others
3. **Testability**: Each component can be tested independently
4. **Flexibility**: Easy to run partial crawls or add new data sources
5. **Debugging**: Better error isolation and component-specific logging
6. **Extensibility**: Clean interfaces for adding new extractors

## Dependencies

See `requirements.txt` for the complete dependency list. Key dependencies include:

- `requests` - HTTP requests
- `PyPDF2` - PDF validation
- `yt-dlp` - YouTube video information
- `youtube-transcript-api` - YouTube transcripts
- `selenium` - Dynamic content scraping
- `beautifulsoup4` - HTML parsing
- `python-dotenv` - Environment configuration

## Troubleshooting

### Import Errors

Make sure you're running from the correct directory and have installed dependencies:

```bash
cd backend/src/service/crawler
pip install -r requirements.txt
```

### Authentication Issues

Verify your Faust key in the `.env` file:

```bash
FAUST_SECRET_KEY=your_actual_key_here
```

### YouTube Access Issues

Configure Webshare proxy credentials if YouTube is blocked:

```bash
WEBSHARE_USERNAME=your_username
WEBSHARE_PASSWORD=your_password
```

### Selenium Issues

Install Chrome/Chromium for Selenium functionality:

```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser

# macOS
brew install --cask google-chrome
```
