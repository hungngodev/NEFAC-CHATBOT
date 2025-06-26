# NEFAC Document Crawler - Complete Package

A comprehensive, self-contained crawler that archives ALL content from the New England First Amendment Coalition (NEFAC) website, including documents, images, blog posts, web pages, and YouTube videos.

## 🚀 Features

### Multi-Source Content Discovery

- **WordPress REST API**: Direct access to media, documents, posts, and news.
- **GraphQL API**: Advanced queries with Faust authentication for enhanced access to posts and their full content.
- **Link Discovery**: Comprehensive URL discovery using the integrated `link-scraper` tool.
- **Selenium Scraping**: Browser automation for extracting clean text from JavaScript-rendered content.
- **Content Extraction**: Robust parsing of post content to find linked documents.
- **YouTube Channel Crawling**: Complete archive of NEFAC YouTube channel with transcript extraction.

### Content Types Archived

- **Documents**: PDFs, Excel files, Word docs, etc., organized by year.
- **Images**: All standard image types (JPG, PNG, GIF).
- **Blog Posts**: Complete, clean HTML of all posts with rich metadata.
- **Web Pages**: All other discoverable HTML pages, saved with meaningful filenames.
- **Plain Text**: Clean text content extracted from key pages via Selenium.
- **YouTube Videos**: Complete video metadata, transcripts, and channel information.
- **Comprehensive Metadata**: Detailed metadata for all content types in separate JSON files.

## 📁 Directory Structure

```
crawler/
├── nefac-document-crawler.py    # Main crawler script
├── setup.py                     # Setup script for easy installation
├── requirements.txt             # Centralized Python dependencies
├── README.md                    # This file
├── .env.example                 # Example configuration file
├── .env                         # Your local configuration (created by setup.py)
├── tools/                       # Integrated tool scripts
│   ├── link-scraper/
│   └── selenium-scraper/
└── nefac_documents/             # Output directory (created after crawl)
    ├── documents/               # PDFs and other documents (by year)
    ├── images/                  # All image files
    ├── content/                 # Blog posts and web pages (HTML and plain text)
    ├── youtube/                 # YouTube video transcripts and metadata
    ├── metadata/                # All metadata JSON files
    └── quarantine/              # Corrupted files
```

## 🛠️ Installation & Setup

1.  **Clone or copy this `crawler` folder** to your desired location.
2.  **Run the setup script.** This will create a Python virtual environment and install all dependencies from the central `requirements.txt` file.
    ```bash
    python3 setup.py
    ```
3.  **Create and configure your `.env` file.** The setup script will create a `.env` file from the `.env.example`. Edit it to add your Faust secret key for enhanced access.
    ```
    FAUST_SECRET_KEY=your_actual_secret_key_here
    ```

## 🚀 Usage

The main crawler orchestrates all the tools automatically. You only need to run the main script.

### Full Crawl (Recommended)

This command runs all discovery methods and downloads all content and metadata.

```bash
python3 nefac-document-crawler.py
```

### YouTube-Only Crawl

To crawl only the NEFAC YouTube channel, use the `--youtube-only` flag. This is much faster if you only need video transcripts and metadata.

```bash
# Crawl YouTube with a 10-15 second delay between videos (default and recommended)
python3 nefac-document-crawler.py --youtube-only

# Adjust the delay (e.g., 20-25 seconds for extra caution)
python3 nefac-document-crawler.py --youtube-only --delay 20
```

### Using a Proxy for YouTube Crawling

If you are running the crawler from a cloud server (AWS, GCP, etc.) or are still getting blocked by YouTube, you can use a rotating residential proxy. The crawler has built-in support for [Webshare.io](https://www.webshare.io/).

1.  Sign up for a Webshare "Residential" proxy plan.
2.  Get your proxy username and password from your Webshare account.
3.  Add your credentials to your `.env` file:
    ```
    WEBSHARE_USERNAME=your_webshare_username
    WEBSHARE_PASSWORD=your_webshare_password
    ```
4.  The crawler will automatically use these credentials when fetching YouTube transcripts. You can also provide them via the command line:
    ```bash
    python3 nefac-document-crawler.py --youtube-only --webshare-username "user" --webshare-password "pass"
    ```

### Other Command-Line Options

- `--metadata-only`: Run all discovery methods but only generate the metadata files without downloading the actual documents, images, or content files. This is useful for a quick run to see what content is available.
- `--skip-web-scraping`: Skip the broad link-discovery and Selenium scraping phases. This will only fetch content directly from the WordPress APIs.
- `--delay SECONDS`: Set a custom base delay (in seconds) between YouTube requests.

---

## 🔧 Integrated Tools

The main crawler script automatically calls the following tools located in the `tools/` directory. You do not need to run them manually.

### Link Scraper (`tools/link-scraper/`)

- **Purpose:** To perform a broad, recursive crawl of the entire website starting from the homepage. It discovers all accessible subpages and attachments (PDFs, images, etc.).
- **Function:** It generates a comprehensive list of URLs that the main crawler then uses to download additional HTML pages and documents that might not be visible through the WordPress APIs.
- **Output:** The results are saved to `nefac_documents/link_discovery_results.json`.

### Selenium Scraper (`tools/selenium-scraper/`)

- **Purpose:** To extract clean, plain text from web pages, especially those that rely on JavaScript to render their content.
- **Function:** It uses a headless browser (Chrome) to load pages, waits for all scripts to execute, and then extracts the visible text content. This is useful for creating a clean text corpus for AI training, free of HTML tags.
- **Output:** The extracted text is saved as `.txt` files in the `nefac_documents/content/` directory, with corresponding metadata in `nefac_documents/metadata/selenium_content_metadata.json`.

---

## 📊 Output Details

### Content Files

- **Documents**: `nefac_documents/documents/YYYY/filename.pdf`
- **Images**: `nefac_documents/images/filename.jpg`
- **Blog Posts**: `nefac_documents/content/post_title.html`
- **Web Pages**: `nefac_documents/content/page_title.html`
- **Plain Text**: `nefac_documents/content/page_name.txt`

### Metadata Files

The crawler produces a separate, detailed metadata file for each type of content. They have different schemas tailored to the content they describe.

- **`documents_metadata.json`**: For all downloaded files (PDFs, DOCs, etc.). Rich with technical details like MIME type, file size, and download headers.
- **`content_metadata.json`**: For all blog posts fetched from the CMS. Rich with editorial details like author, categories, tags, and featured images.
- **`images_metadata.json`**: For all downloaded image files.
- **`html_pages_metadata.json`**: For generic web pages discovered by the link scraper.
- **`selenium_content_metadata.json`**: For the plain text files extracted by Selenium.
- **`youtube_metadata.json`**: For all YouTube videos with comprehensive metadata including view counts, likes, comments, transcripts, and video information.
- **`crawl_summary.json`**: A summary of the entire crawl operation, including counts and timing.

## 🔍 Troubleshooting

- **YouTube IP Bans:** If you see `RequestBlocked` or `IpBlocked` errors in the log, your IP has been temporarily blocked by YouTube.
  - **Solution 1 (Recommended):** Use the `--delay` flag to slow down requests (e.g., `--delay 15`). The default is 10 seconds.
  - **Solution 2 (Most Reliable):** Use a rotating residential proxy service like [Webshare.io](https://www.webshare.io/) as described in the "Usage" section. This is the best long-term solution.
- **Missing Faust Key:** If you see errors related to GraphQL, ensure your `.env` file exists and contains a valid `FAUST_SECRET_KEY`.
- **Permission Errors:** Ensure you have write access to the `crawler` directory.
- **Selenium Issues:** The `setup.py` script uses `webdriver-manager` to automatically handle the Chrome driver. If you encounter issues, ensure you have Google Chrome installed. For headless servers, you may need to install it manually.
- **Logs:** The `nefac_crawler.log` file contains a detailed, timestamped log of all operations, warnings, and errors. This should be the first place you look if something goes wrong.

## 📝 Development

### Adding New Sources

1. Add new discovery method to crawler
2. Update metadata structure
3. Add to main crawl sequence

### Customization

- Modify file organization in `download_document()` method
- Add new content types in `image_extensions` and `document_types`
- Customize metadata fields as needed

## 📄 License

This crawler is designed for archival and research purposes. Please respect the source website's terms of service and robots.txt.

## 🤝 Support

For issues or questions:

1. Check the logs in `nefac_crawler.log`
2. Review the crawl summary
3. Ensure all dependencies are installed

---

**Complete NEFAC Archive**: This crawler creates a comprehensive, searchable archive of all NEFAC content with full metadata and organization.
