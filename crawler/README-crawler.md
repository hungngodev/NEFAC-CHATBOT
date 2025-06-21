# NEFAC Document Crawler - Comprehensive Edition

A powerful Python crawler that discovers and downloads ALL documents from the New England First Amendment Coalition (NEFAC) website using multiple discovery methods and optional Faust secret key authentication.

## 🚀 Features

### Multi-Source Document Discovery

- **WordPress REST API**: Direct media/documents, posts, news, attachments
- **GraphQL API**: Advanced queries with optional Faust authentication
- **Web Scraping**: Direct document link discovery from web pages
- **Link Discovery Tool**: Integration with existing link-scraper
- **Content Extraction**: Parse document links from post content (requires Faust key)

### Enhanced Capabilities

- **Faust Authentication**: Use secret key for enhanced GraphQL access
- **Comprehensive Coverage**: 7 different discovery methods
- **Duplicate Prevention**: Smart deduplication across sources
- **Progress Tracking**: Detailed logging and statistics
- **Error Handling**: Robust error recovery and reporting
- **Flexible Output**: Metadata-only or full file downloads

### Document Types Supported

- PDFs, Word documents (DOC/DOCX)
- Excel spreadsheets (XLS/XLSX)
- PowerPoint presentations (PPT/PPTX)
- CSV files, text files, and more

## 📁 Project Structure

```
crawler/
├── nefac-document-crawler.py    # Main comprehensive crawler
├── .env                         # Configuration file (create from template)
├── README-crawler.md           # This file
└── requirements.txt            # Python dependencies
```

## 🛠️ Installation

1. **Navigate to the crawler directory:**

   ```bash
   cd crawler
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your FAUST_SECRET_KEY
   ```

## ⚙️ Configuration

### Environment Variables (.env file)

```bash
# Required for enhanced GraphQL access
FAUST_SECRET_KEY=your_faust_secret_key_here

# Optional crawler settings
OUTPUT_DIR=nefac_documents
DOWNLOAD_FILES=true
MAX_CONCURRENT_DOWNLOADS=5
```

### Faust Secret Key

The Faust secret key enables:

- **Authenticated GraphQL queries** with full access
- **Content extraction** from post text
- **Enhanced document discovery** from private content
- **Better rate limits** and access permissions

**To get your Faust secret key:**

1. Contact the NEFAC website administrator
2. Request access to the Faust GraphQL plugin
3. Add the key to your `.env` file

## 🚀 Usage

### Basic Usage (Public APIs Only)

```bash
# Run with default settings
python nefac-document-crawler.py

# Metadata only (no file downloads)
python nefac-document-crawler.py --metadata-only

# Custom output directory
python nefac-document-crawler.py --output-dir my_documents
```

### Enhanced Usage (With Faust Authentication)

```bash
# Using environment variable
export FAUST_SECRET_KEY="your_key_here"
python nefac-document-crawler.py

# Using command line argument
python nefac-document-crawler.py --faust-key "your_key_here"

# Combined options
python nefac-document-crawler.py \
  --faust-key "your_key_here" \
  --output-dir enhanced_documents \
  --metadata-only
```

### Advanced Options

```bash
# Filter by document types
python nefac-document-crawler.py --document-types pdf docx

# Skip web scraping (API only)
python nefac-document-crawler.py --skip-web-scraping

# Full example with all options
python nefac-document-crawler.py \
  --faust-key "your_key_here" \
  --output-dir nefac_docs \
  --document-types pdf docx xlsx \
  --metadata-only
```

## 📊 Output Structure

```
nefac_documents/
├── documents/                    # Downloaded files (if enabled)
│   ├── 2024/
│   ├── 2023/
│   └── ...
├── metadata/
│   └── documents_metadata.json   # Complete document metadata
├── content/                      # Extracted content (if applicable)
└── crawl_summary.json           # Crawl statistics and summary
```

### Metadata Format

Each document includes:

```json
{
  "id": "unique_identifier",
  "title": "Document Title",
  "source_url": "https://nefac.org/path/to/document.pdf",
  "mime_type": "application/pdf",
  "date": "2024-01-15T10:30:00",
  "modified": "2024-01-15T10:30:00",
  "alt_text": "Alternative text",
  "description": "Document description",
  "caption": "Document caption",
  "source": "graphql_authenticated",
  "file_size": 1024000,
  "related_post": {
    "id": "post_id",
    "title": "Post Title",
    "slug": "post-slug"
  }
}
```

### Crawl Summary

```json
{
  "total_documents": 415,
  "downloaded_documents": 410,
  "failed_downloads": 5,
  "document_types": {
    "pdf": 300,
    "docx": 80,
    "xlsx": 35
  },
  "sources": {
    "wordpress_rest_api": 150,
    "graphql_api": 50,
    "graphql_authenticated": 100,
    "web_scraping": 50,
    "link_discovery": 30,
    "content_extraction": 35
  },
  "start_time": "2024-01-15T10:00:00",
  "end_time": "2024-01-15T10:15:00",
  "duration_seconds": 900
}
```

## 🔍 Discovery Methods

### 1. WordPress REST API

- **Endpoint**: `/wp-json/wp/v2/media`
- **Documents**: Direct media uploads
- **Authentication**: Not required
- **Coverage**: ~150 documents

### 2. GraphQL API (Public)

- **Endpoint**: `/graphql`
- **Documents**: Media items via GraphQL
- **Authentication**: Not required
- **Coverage**: ~50 documents

### 3. GraphQL API (Authenticated)

- **Endpoint**: `/graphql` with Faust key
- **Documents**: Enhanced media access
- **Authentication**: FAUST_SECRET_KEY required
- **Coverage**: ~100 additional documents

### 4. Content Extraction

- **Method**: Parse post content for document links
- **Documents**: Embedded document references
- **Authentication**: FAUST_SECRET_KEY required
- **Coverage**: ~35 additional documents

### 5. Post Attachments

- **Method**: Extract from post embedded media
- **Documents**: Documents attached to posts
- **Authentication**: Not required
- **Coverage**: ~50 documents

### 6. News Post Attachments

- **Method**: Extract from news custom post type
- **Documents**: Documents in news articles
- **Authentication**: Not required
- **Coverage**: ~30 documents

### 7. Web Scraping

- **Method**: Direct HTML parsing
- **Documents**: Document links on web pages
- **Authentication**: Not required
- **Coverage**: ~50 documents

### 8. Link Discovery Tool

- **Method**: Integration with existing link-scraper
- **Documents**: Deep link discovery
- **Authentication**: Not required
- **Coverage**: ~30 documents

## 📈 Performance Comparison

| Method           | Documents Found | Requires Auth | Speed  |
| ---------------- | --------------- | ------------- | ------ |
| Public APIs Only | ~280            | No            | Fast   |
| With Faust Key   | ~415            | Yes           | Medium |
| Full Discovery   | ~415            | Yes           | Slow   |

## 🐛 Troubleshooting

### Common Issues

**1. Permission Denied Errors**

```bash
# Make sure you have write permissions
chmod 755 nefac_documents/
```

**2. Network Timeouts**

```bash
# Increase timeout or retry
python nefac-document-crawler.py --output-dir retry_docs
```

**3. Faust Key Not Working**

```bash
# Verify your key is correct
echo $FAUST_SECRET_KEY
# Check the .env file
cat .env
```

**4. Missing Dependencies**

```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

### Log Files

- **Main log**: `nefac_crawler.log` (in crawler directory)
- **Detailed output**: Check console output for real-time progress

## 🔧 Development

### Adding New Document Types

Edit the `document_types` dictionary in the crawler:

```python
self.document_types = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    # Add your new type here
    "application/your-mime-type": "extension"
}
```

### Adding New Discovery Methods

1. Create a new method in the `NEFACDocumentCrawler` class
2. Add it to the `crawl()` method
3. Update the statistics tracking

### Testing

```bash
# Test with a small subset
python nefac-document-crawler.py --metadata-only --output-dir test_output

# Test specific document types
python nefac-document-crawler.py --document-types pdf
```

## 📝 License

This crawler is designed for educational and research purposes. Please respect the NEFAC website's terms of service and robots.txt file.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Review the log files
3. Create an issue with detailed information

---

**Note**: This crawler is designed to be respectful of the NEFAC website. It includes rate limiting and proper error handling to avoid overwhelming the server.
