# NEFAC Crawler Documentation

## 1. Overview

The NEFAC Crawler is a robust, custom-built Python application designed to harvest content from the New England First Amendment Coalition (NEFAC) ecosystem. It is not based on Scrapy; instead, it uses a modular architecture with `requests`, `ThreadPoolExecutor`, and specialized extractors for different content sources.

- **Framework**: Custom Python 3.11+ application.
- **Key Libraries**: `requests` (HTTP), `tqdm` (Progress), `yt-dlp` (YouTube), `pydantic` (Validation).
- **Architecture**: Orchestrator pattern (`NEFACCrawler` class) managing specialized Extractors and Downloaders.
- **Capabilities**:
  - **Multi-Source**: WordPress (REST API) and YouTube (Channel/Videos).
  - **Incremental Crawling**: Only fetches content modified since the last run.
  - **Rigid Validation**: Ensures downloaded files match metadata (size, headers).
  - **Fail-Fast & Retry**: Intelligent retry logic with exponential backoff.

## 2. Core Flow

The crawler's entry point is `backend/src/service/crawler/run.py`.

### 2.1 Execution Pipeline

1.  **Initialization**: `NEFACCrawler` initializes with configuration.
2.  **Extraction (`extract_safe`)**:
    - **WordPress**: Queries `https://nefac.org/wp-json/wp/v2/` for posts, pages, news, and media.
    - **YouTube**: Uses `yt-dlp` to fetch channel videos and `youtube_transcript_api` for transcripts.
3.  **Deduplication**: Checks against existing metadata to skip already processed items (if incremental).
4.  **Download (`download_parallel`)**:
    - Uses `ThreadPoolExecutor` to download files in parallel.
    - Validates file integrity (PDF headers, file size) immediately after download.
    - Moves corrupted files to a `quarantine/` directory.
5.  **Persistence**:
    - Saves files to type-specific directories (`pdf/`, `html/`, `youtube/`).
    - Saves metadata to JSON files in `metadata/`.
6.  **Validation**: Runs a final `RigidValidator` pass to ensure synchronization between filesystem and metadata.

### 2.2 Modules

- **`run.py`**: CLI entry point and orchestration logic.
- **`extractors/`**:
  - `wordpress_extractor.py`: Handles WP REST API pagination and content parsing.
  - `youtube_extractor.py`: Fetches video metadata and saves transcripts as `.txt`.
- **`downloaders/`**:
  - `document_downloader.py`: Handles HTTP downloads, retries, and file validation.
  - `metadata_manager.py`: Manages JSON metadata storage and incremental state.

## 3. Configuration & Arguments

The crawler is configured via **Command Line Arguments** and **Environment Variables**.

### 3.1 CLI Arguments

Run via `python src/service/crawler/run.py`:

| Flag                | Description                                           | Default           |
| :------------------ | :---------------------------------------------------- | :---------------- |
| `--youtube-only`    | Crawl only YouTube content.                           | `False`           |
| `--wordpress-only`  | Crawl only WordPress content.                         | `False`           |
| `--sync-only`       | Skip crawling; only run validation on existing files. | `False`           |
| `--incremental`     | Only fetch new/modified content since last run.       | `False`           |
| `--workers N`       | Number of parallel download workers.                  | `5`               |
| `--output-dir PATH` | Custom output directory.                              | `nefac_documents` |
| `--debug`           | Enable debug logging.                                 | `False`           |
| `--no-validation`   | Skip the post-crawl validation step.                  | `False`           |
| `--fix-issues`      | Automatically fix metadata/file sync issues.          | `False`           |

### 3.2 Environment Variables (`.env`)

Loaded via `src/service/crawler/core/config.py`:

| Variable          | Description                                          | Default             |
| :---------------- | :--------------------------------------------------- | :------------------ |
| `OUTPUT_DIR`      | Base directory for downloads.                        | `nefac_documents`   |
| `WORDPRESS_URL`   | Base URL for WordPress site.                         | `https://nefac.org` |
| `YOUTUBE_API_KEY` | (Optional) For YouTube API (uses `yt-dlp` fallback). | `None`              |
| `MAX_WORKERS`     | Default parallel workers.                            | `10`                |
| `REQUEST_DELAY`   | Delay between requests (seconds).                    | `0.1`               |
| `YOUTUBE_DELAY`   | Base delay for YouTube requests.                     | `45.0`              |

## 4. Data Output

Data is structured hierarchically in the `OUTPUT_DIR` (default: `nefac_documents/`).

### 4.1 Directory Structure

```text
nefac_documents/
├── pdf/                # PDF documents
├── html/               # HTML captures of web pages
├── youtube/            # Video transcripts (.txt)
├── documents/          # Word/Text documents
├── xlsx/               # Spreadsheets
├── images/             # Downloaded images
├── metadata/           # JSON Metadata
│   ├── pdf_metadata.json
│   ├── html_metadata.json
│   ├── youtube_metadata.json
│   └── ...
└── quarantine/         # Corrupted files
```

### 4.2 Metadata Schema

Metadata is stored as JSON arrays. Example (`pdf_metadata.json`):

```json
[
  {
    "id": "12345",
    "title": "Public Records Guide",
    "filename": "public-records-guide.pdf",
    "source_url": "https://nefac.org/...",
    "date": "2023-01-01T12:00:00",
    "mime_type": "application/pdf",
    "file_size": 102400,
    "file_path": "pdf/public-records-guide.pdf",
    "source": "wordpress"
  }
]
```

## 5. Dependencies & Setup

### 5.1 Requirements

Defined in `backend/pyproject.toml`. Key dependencies:

- `requests`: HTTP client.
- `tqdm`: Progress bars.
- `yt-dlp`: YouTube extraction.
- `youtube-transcript-api`: Transcript fetching.
- `pydantic`: Data validation.
- `PyPDF2`: PDF validation.

### 5.2 Running the Crawler

From the `backend/` directory:

```bash
# 1. Install dependencies
poetry install

# 2. Run full crawl (fresh)
poetry run python src/service/crawler/run.py

# 3. Run incremental crawl (daily job)
poetry run python src/service/crawler/run.py --incremental

# 4. Run only YouTube
poetry run python src/service/crawler/run.py --youtube-only --workers 2
```

## 2. Core Flow

### 2.1 Execution Loop (`NEFACCrawler.crawl`)

1.  **Initialization**: Loads configuration and incremental state (last crawl date).
2.  **Extraction**:
    - **WordPress**: Calls `WordPressExtractor` to fetch posts/pages via REST API.
    - **YouTube**: Calls `YouTubeExtractor` to fetch video metadata and transcripts via `yt-dlp`.
3.  **Download**:
    - Uses `download_parallel` with `ThreadPoolExecutor` (default 5 workers).
    - Downloads PDFs, images, and raw HTML content.
4.  **Validation**:
    - Runs `RigidValidator` to ensure every metadata entry has a corresponding file on disk.
    - Auto-fixes missing files if `--fix-issues` is enabled.

### 2.2 Extractors
*   **`WordPressExtractor`**:
    *   Iterates over `/wp-json/wp/v2/` endpoints (posts, pages, media).
    *   Handles pagination (`X-WP-TotalPages`) and exponential backoff.
*   **`YouTubeExtractor`**:
    *   Uses `yt-dlp` to extract video metadata and auto-generated captions (transcripts).
    *   Skips videos without transcripts (configurable).

### 2.3 Extractor Details (`src/service/crawler/extractors/`)
The crawler uses specialized logic for each source to ensure robustness.

| Component | Logic & Behavior |
| :--- | :--- |
| **WordPress** | • **Endpoints**: `posts`, `pages`, `news`, `media`.<br>• **Retries**: 5 retries with exponential backoff on 429/50x errors.<br>• **Auth**: Optional Basic Auth via `WORDPRESS_USERNAME`. |
| **YouTube** | • **Tool**: `yt-dlp` (embedded).<br>• **Delay**: Dynamic backoff (35s - 180s) to avoid IP bans.<br>• **Filter**: Skips videos without auto-generated English captions. |
| **File Mapping** | • `.pdf` -> `pdf/`<br>• `.mp4` -> `videos/`<br>• `.html` -> `html/`<br>• `.doc` -> `documents/` |

## 3. Configuration & Arguments

### 3.1 Command Line Interface (`run.py`)

| Argument       | Flag               | Default           | Description                             |
| :------------- | :----------------- | :---------------- | :-------------------------------------- |
| **Mode**       | `--youtube-only`   | `False`           | Crawl only YouTube channel.             |
|                | `--wordpress-only` | `False`           | Crawl only WordPress site.              |
|                | `--sync-only`      | `False`           | Skip crawling, only run validation.     |
| **General**    | `--incremental`    | `False`           | Only fetch content newer than last run. |
|                | `--workers`        | `5`               | Number of parallel download threads.    |
|                | `--output-dir`     | `nefac_documents` | Custom output directory.                |
| **Validation** | `--fix-issues`     | `False`           | Attempt to re-download missing files.   |
|                | `--no-validation`  | `False`           | Skip the post-crawl check.              |

### 3.2 Environment Variables (`.env`)

Managed via `src/service/crawler/core/config.py`.

- `WORDPRESS_USERNAME` / `WORDPRESS_PASSWORD`: Optional Basic Auth for WP API.
- `YOUTUBE_API_KEY`: Optional, for API-based metadata (fallback to `yt-dlp`).
- `CRAWLER_USER_AGENT`: Custom User-Agent string.

## 4. Data Output

### 4.1 Directory Structure

The crawler organizes output by file type:

```
nefac_documents/
├── html/           # Raw HTML content from WordPress
├── pdf/            # Downloaded PDF documents
├── videos/         # YouTube video metadata/transcripts
├── metadata/       # JSON metadata files (source of truth)
└── ...
```

### 4.2 Metadata Schema (`src/schemas/metadata.py`)

Every downloaded file has a corresponding JSON entry in `metadata/`:

```json
{
  "id": "12345",
  "title": "Public Records Guide",
  "source_url": "https://nefac.org/guide.pdf",
  "file_path": "pdf/guide.pdf",
  "date": "2023-01-01",
  "mime_type": "application/pdf"
}
```

## 5. Dependencies & Setup

### 5.1 Key Libraries

- `requests`: HTTP client for WordPress API.
- `yt-dlp`: Robust YouTube extraction.
- `beautifulsoup4`: HTML parsing/cleaning.
- `tqdm`: Progress bars.
- `pydantic`: Data validation.

### 5.2 Development Setup

**Location**: `backend/`
**Entry Point**: `src.service.crawler.run`

1.  **Install Dependencies**:
    ```bash
    cd backend
    poetry install
    ```

2.  **Run Crawler**:
    Execute the module via Poetry:

    **Full Crawl (WordPress + YouTube)**:
    ```bash
    poetry run python -m src.service.crawler.run --mode full
    ```

    **Incremental Crawl (New Content Only)**:
    ```bash
    poetry run python -m src.service.crawler.run --incremental
    ```

    **Specific Source**:
    ```bash
    poetry run python -m src.service.crawler.run --mode youtube --workers 2
    ```
