#!/usr/bin/env python3
"""
NEFAC Document Crawler - Comprehensive Edition with Faust Authentication

This script crawls ALL documents from the New England First Amendment Coalition (NEFAC)
using multiple endpoints and sources with optional Faust secret key authentication:

1. WordPress REST API:
   - /wp-json/wp/v2/posts - News articles with embedded media
   - /wp-json/wp/v2/media - Direct media/documents
   - /wp-json/wp/v2/news - Custom news post type
   - /wp-json/wp/v2/attachments - Document attachments

2. GraphQL API (Enhanced with Faust Secret Key):
   - /graphql - Advanced queries for media items
   - Authenticated access for content extraction
   - Full post content analysis

3. Web Scraping (Enhanced):
   - Direct document links from web pages
   - Embedded document references
   - Link discovery using existing tools
   - Selenium-based content extraction

Features:
- Fetches all document types (PDFs, Word docs, Excel, etc.)
- Downloads files with organized directory structure
- Saves comprehensive metadata as JSON
- Handles pagination automatically
- Progress tracking and error handling
- Configurable filters and options
- Multiple source discovery methods
- Web scraping integration for complete coverage
- Optional Faust secret key for enhanced GraphQL access
- Content extraction from post text
"""

import os
import json
import requests
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin
from pathlib import Path
import argparse
from typing import List, Dict, Any, Optional
import logging
import re
import subprocess
import sys
import mimetypes
from dotenv import load_dotenv
try:
    import PyPDF2
except ImportError:
    print("PyPDF2 is not installed. Please install it with: pip install PyPDF2")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nefac_crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NEFACDocumentCrawler:
    def __init__(self, output_dir: str = "nefac_documents", download_files: bool = True, faust_key: Optional[str] = None):
        self.base_url = "https://nefac.org"
        self.output_dir = Path(output_dir)
        self.download_files = download_files
        self.faust_key = faust_key
        
        # Create output directories
        self.documents_dir = self.output_dir / "documents"
        self.metadata_dir = self.output_dir / "metadata"
        self.content_dir = self.output_dir / "content"
        self.quarantine_dir = self.output_dir / "quarantine"
        self.images_dir = self.output_dir / "images"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # API endpoints
        self.endpoints = {
            "posts": f"{self.base_url}/wp-json/wp/v2/posts",
            "media": f"{self.base_url}/wp-json/wp/v2/media",
            "news": f"{self.base_url}/wp-json/wp/v2/news",
            "graphql": f"{self.base_url}/graphql"
        }
        
        # Document types to look for
        self.document_types = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "application/msword": "doc",
            "application/vnd.ms-excel": "xls",
            "application/vnd.ms-powerpoint": "ppt",
            "text/csv": "csv",
            "text/plain": "txt"
        }
        
        # File extensions to look for in web scraping
        self.document_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
            '.csv', '.txt', '.rtf', '.odt', '.ods', '.odp'
        }
        
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        
        # Statistics
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
                "content_extraction": 0
            },
            "start_time": datetime.now(),
            "end_time": None,
            "mime_types": {}
        }
        
        # Track discovered documents to avoid duplicates
        self.discovered_documents = set()
        
    def get_graphql_headers(self):
        """Get headers for authenticated GraphQL requests."""
        headers = {
            'Content-Type': 'application/json',
        }
        
        if self.faust_key:
            headers['Authorization'] = f'Bearer {self.faust_key}'
            logger.info("Using authenticated GraphQL requests with FAUST_SECRET_KEY")
        else:
            logger.info("Using public GraphQL requests (no authentication)")
            
        return headers
        
    def fetch_with_pagination(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fetch all items from a paginated endpoint."""
        if params is None:
            params = {}
        
        all_items = []
        page = 1
        per_page = 100
        
        while True:
            params.update({
                'page': page,
                'per_page': per_page,
                '_embed': 'true'
            })
            
            try:
                response = requests.get(endpoint, params=params, timeout=30)
                response.raise_for_status()
                items = response.json()
                
                if not items:
                    break
                    
                all_items.extend(items)
                logger.info(f"Fetched page {page} from {endpoint} ({len(items)} items)")
                
                # Check if we've reached the end
                if len(items) < per_page:
                    break
                    
                page += 1
                time.sleep(0.5)  # Be respectful to the server
                
            except Exception as e:
                logger.error(f"Error fetching from {endpoint} page {page}: {e}")
                break
                
        return all_items
    
    def fetch_wordpress_media(self) -> List[Dict]:
        """Fetch all media items from WordPress REST API."""
        logger.info("Fetching media items from WordPress REST API...")
        
        all_media = []
        
        # Fetch all media items
        media_items = self.fetch_with_pagination(self.endpoints["media"])
        
        for item in media_items:
            mime_type = item.get('mime_type', '')
            
            # Check if it's a document type we're interested in
            if any(doc_type in mime_type for doc_type in self.document_types.keys()):
                document_info = {
                    'id': item['id'],
                    'title': item['title']['rendered'],
                    'source_url': item['source_url'],
                    'mime_type': mime_type,
                    'date': item['date'],
                    'modified': item['modified'],
                    'alt_text': item.get('alt_text', ''),
                    'description': item.get('description', {}).get('rendered', ''),
                    'caption': item.get('caption', {}).get('rendered', ''),
                    'source': 'wordpress_rest_api',
                    'file_size': item.get('media_details', {}).get('filesize', 0)
                }
                
                all_media.append(document_info)
                self.stats['sources']['wordpress_rest_api'] += 1
                
        logger.info(f"Found {len(all_media)} documents via WordPress REST API")
        return all_media
    
    def fetch_graphql_media(self) -> List[Dict]:
        """Fetch media items using GraphQL API."""
        logger.info("Fetching media items from GraphQL API...")
        
        query = """
        query GetMediaItems($first: Int!, $after: String) {
            mediaItems(first: $first, after: $after) {
                nodes {
                    id
                    title
                    sourceUrl
                    mimeType
                    date
                    modified
                    altText
                    description
                    caption
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        all_media = []
        has_next_page = True
        after_cursor = None
        
        while has_next_page:
            try:
                variables = {
                    "first": 100,
                    "after": after_cursor
                }
                
                response = requests.post(
                    self.endpoints["graphql"],
                    json={"query": query, "variables": variables},
                    headers=self.get_graphql_headers(),
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    break
                
                media_items = data['data']['mediaItems']['nodes']
                page_info = data['data']['mediaItems']['pageInfo']
                
                for item in media_items:
                    mime_type = item.get('mimeType', '')
                    
                    # Check if it's a document type we're interested in
                    if any(doc_type in mime_type for doc_type in self.document_types.keys()):
                        document_info = {
                            'id': item['id'],
                            'title': item['title'],
                            'source_url': item['sourceUrl'],
                            'mime_type': mime_type,
                            'date': item['date'],
                            'modified': item['modified'],
                            'alt_text': item.get('altText', ''),
                            'description': item.get('description', ''),
                            'caption': item.get('caption', ''),
                            'source': 'graphql_authenticated' if self.faust_key else 'graphql_api',
                            'file_size': 0  # GraphQL doesn't provide file size
                        }
                        
                        all_media.append(document_info)
                        if self.faust_key:
                            self.stats['sources']['graphql_authenticated'] += 1
                        else:
                            self.stats['sources']['graphql_api'] += 1
                
                has_next_page = page_info['hasNextPage']
                after_cursor = page_info['endCursor']
                
                logger.info(f"Fetched {len(media_items)} items from GraphQL API")
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error fetching from GraphQL API: {e}")
                break
                
        logger.info(f"Found {len(all_media)} documents via GraphQL API")
        return all_media
    
    def graphql_request(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Make a GraphQL request with proper headers."""
        try:
            response = requests.post(
                self.endpoints["graphql"],
                json={'query': query, 'variables': variables or {}},
                headers=self.get_graphql_headers(),
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GraphQL request failed: {e}")
            return None

    def fetch_posts_with_content(self) -> List[Dict]:
        """Fetch all posts using GraphQL to extract documents from content."""
        logger.info("Fetching posts with full content from GraphQL API...")
        
        # GraphQL query to fetch posts with content
        query = """
        query GetPostsWithContent($first: Int!, $after: String) {
            posts(first: $first, after: $after) {
                nodes {
                    id
                    databaseId
                    slug
                    title
                    date
                    modified
                    content
                    excerpt
                    author {
                        node {
                            name
                            slug
                        }
                    }
                    categories {
                        nodes {
                            name
                            slug
                        }
                    }
                    tags {
                        nodes {
                            name
                            slug
                        }
                    }
                    uri
                    link
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        all_posts = []
        has_next_page = True
        after_cursor = None
        
        while has_next_page:
            variables = {
                "first": 100,
                "after": after_cursor
            }
            
            try:
                response = self.graphql_request(query, variables)
                if not response or 'data' not in response:
                    logger.error("Invalid GraphQL response")
                    break
                    
                data = response['data']['posts']
                posts = data['nodes']
                page_info = data['pageInfo']
                
                all_posts.extend(posts)
                
                has_next_page = page_info['hasNextPage']
                after_cursor = page_info['endCursor']
                
                logger.info(f"Fetched {len(posts)} posts (total: {len(all_posts)})")
                
            except Exception as e:
                logger.error(f"Error fetching posts: {e}")
                break
        
        logger.info(f"Total posts fetched: {len(all_posts)}")
        
        # Save content files and extract documents
        documents_found = []
        content_metadata = []
        
        for post in all_posts:
            try:
                # Save the content to a file
                post_id = post['databaseId']
                filename = f"{post_id}.html"
                filepath = self.content_dir / filename
                
                # Create content metadata entry
                content_meta = {
                    "id": post_id,
                    "title": post['title'],
                    "slug": post['slug'],
                    "date": post['date'],
                    "modified": post['modified'],
                    "uri": post['uri'],
                    "link": post['link'],
                    "excerpt": post['excerpt'],
                    "author": post['author']['node']['name'] if post['author'] and post['author']['node'] else None,
                    "author_slug": post['author']['node']['slug'] if post['author'] and post['author']['node'] else None,
                    "categories": [cat['name'] for cat in post['categories']['nodes']] if post['categories'] else [],
                    "category_slugs": [cat['slug'] for cat in post['categories']['nodes']] if post['categories'] else [],
                    "tags": [tag['name'] for tag in post['tags']['nodes']] if post['tags'] else [],
                    "tag_slugs": [tag['slug'] for tag in post['tags']['nodes']] if post['tags'] else [],
                    "content_length": len(post['content']),
                    "source_url": f"https://nefac.org{post['uri']}",
                    "mime_type": "text/html",
                    "source": "graphql_content",
                    "file_path": str(filepath.relative_to(self.output_dir)),
                    "file_size": 0  # Will be updated after saving
                }
                
                # Save the HTML content
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(post['content'])
                
                # Update file size
                content_meta['file_size'] = filepath.stat().st_size
                content_metadata.append(content_meta)
                
                # Extract document links from content
                doc_links = self.extract_documents_from_content(post['content'])
                for link in doc_links:
                    document_info = {
                        'title': f"Document from {post['title']}",
                        'source_url': link,
                        'date': post['date'],
                        'modified': post['modified'],
                        'source': 'content_extraction',
                        'post_id': post_id,
                        'post_title': post['title'],
                        'post_url': f"https://nefac.org{post['uri']}"
                    }
                    documents_found.append(document_info)
                
            except Exception as e:
                logger.error(f"Error processing post {post.get('databaseId', 'unknown')}: {e}")
        
        # Save content metadata
        content_metadata_file = self.metadata_dir / "content_metadata.json"
        with open(content_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(content_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved metadata for {len(content_metadata)} content files to {content_metadata_file}")
        logger.info(f"Extracted {len(documents_found)} document links from content")
        
        return documents_found
    
    def fetch_posts_with_attachments(self) -> List[Dict]:
        """Fetch posts and extract any document attachments."""
        logger.info("Fetching posts and extracting document attachments...")
        
        posts = self.fetch_with_pagination(self.endpoints["posts"])
        documents = []
        
        for post in posts:
            # Check embedded media
            if '_embedded' in post and 'wp:featuredmedia' in post['_embedded']:
                for media in post['_embedded']['wp:featuredmedia']:
                    mime_type = media.get('mime_type', '')
                    if any(doc_type in mime_type for doc_type in self.document_types.keys()):
                        document_info = {
                            'id': media['id'],
                            'title': media['title']['rendered'],
                            'source_url': media['source_url'],
                            'mime_type': mime_type,
                            'date': media['date'],
                            'modified': media['modified'],
                            'alt_text': media.get('alt_text', ''),
                            'description': media.get('description', {}).get('rendered', ''),
                            'caption': media.get('caption', {}).get('rendered', ''),
                            'source': 'wordpress_rest_api',
                            'file_size': media.get('media_details', {}).get('filesize', 0),
                            'related_post': {
                                'id': post['id'],
                                'title': post['title']['rendered'],
                                'slug': post['slug']
                            }
                        }
                        documents.append(document_info)
        
        logger.info(f"Found {len(documents)} document attachments in posts")
        return documents
    
    def fetch_news_with_attachments(self) -> List[Dict]:
        """Fetch news custom post type and extract document attachments."""
        logger.info("Fetching news posts and extracting document attachments...")
        
        news_posts = self.fetch_with_pagination(self.endpoints["news"])
        documents = []
        
        for post in news_posts:
            # Check embedded media
            if '_embedded' in post and 'wp:featuredmedia' in post['_embedded']:
                for media in post['_embedded']['wp:featuredmedia']:
                    mime_type = media.get('mime_type', '')
                    if any(doc_type in mime_type for doc_type in self.document_types.keys()):
                        document_info = {
                            'id': media['id'],
                            'title': media['title']['rendered'],
                            'source_url': media['source_url'],
                            'mime_type': mime_type,
                            'date': media['date'],
                            'modified': media['modified'],
                            'alt_text': media.get('alt_text', ''),
                            'description': media.get('description', {}).get('rendered', ''),
                            'caption': media.get('caption', {}).get('rendered', ''),
                            'source': 'wordpress_rest_api',
                            'file_size': media.get('media_details', {}).get('filesize', 0),
                            'related_news_post': {
                                'id': post['id'],
                                'title': post['title']['rendered'],
                                'slug': post['slug']
                            }
                        }
                        documents.append(document_info)
        
        logger.info(f"Found {len(documents)} document attachments in news posts")
        return documents
    
    def run_link_scraper(self) -> List[str]:
        """Run the existing link-scraper tool to discover document links."""
        logger.info("Running link-scraper tool to discover document links...")
        
        try:
            # Check if the link-scraper tool exists
            link_scraper_path = Path("tools/link-scraper/main.py")
            if not link_scraper_path.exists():
                logger.warning("Link-scraper tool not found at tools/link-scraper/main.py")
                return []
            
            # Run the link-scraper with attachment discovery
            output_file = self.output_dir / "link_discovery_results.json"
            cmd = [
                sys.executable, str(link_scraper_path),
                self.base_url,
                "--include-attachments",
                "--max-depth", "3",
                "--output", str(output_file)
            ]
            
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("Link-scraper completed successfully")
                
                # Parse the results to find document links
                if output_file.exists():
                    with open(output_file, 'r') as f:
                        link_data = json.load(f)
                    
                    document_links = []
                    for url, data in link_data.items():
                        if self.is_document_url(url):
                            document_links.append(url)
                    
                    logger.info(f"Found {len(document_links)} document links via link-scraper")
                    return document_links
                else:
                    logger.warning("Link-scraper output file not found")
                    return []
            else:
                logger.error(f"Link-scraper failed: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error running link-scraper: {e}")
            return []
    
    def is_document_url(self, url: str) -> bool:
        """Check if a URL points to a document."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in self.document_extensions)
    
    def extract_documents_from_content(self, content: str) -> List[str]:
        """Extract document URLs from HTML content."""
        # Look for PDF and document links
        document_patterns = [
            r'href=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']',
            r'src=["\']([^"\']*\.(?:pdf|doc|docx|xls|xlsx|ppt|pptx|csv))["\']'
        ]
        
        documents = []
        for pattern in document_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match.startswith('http'):
                    documents.append(match)
                else:
                    documents.append(urljoin(self.base_url, match))
        
        return list(set(documents))  # Remove duplicates
    
    def scrape_web_pages_for_documents(self) -> List[Dict]:
        """Scrape web pages to find document links not in the API."""
        logger.info("Scraping web pages for document links...")
        
        # Get some key pages to scrape
        pages_to_scrape = [
            f"{self.base_url}/",
            f"{self.base_url}/news/",
            f"{self.base_url}/about/",
            f"{self.base_url}/contact/"
        ]
        
        documents = []
        
        for page_url in pages_to_scrape:
            try:
                response = requests.get(page_url, timeout=30)
                response.raise_for_status()
                
                # Extract document links from HTML
                doc_links = self.extract_documents_from_content(response.text)
                
                for link in doc_links:
                    if link not in self.discovered_documents:
                        document_info = {
                            'id': f"web_{len(documents)}",
                            'title': self.extract_title_from_url(link),
                            'source_url': link,
                            'mime_type': self.guess_mime_type(link),
                            'date': datetime.now().isoformat(),
                            'modified': datetime.now().isoformat(),
                            'alt_text': '',
                            'description': f'Found via web scraping on {page_url}',
                            'caption': '',
                            'source': 'web_scraping',
                            'file_size': 0,
                            'discovered_on_page': page_url
                        }
                        
                        documents.append(document_info)
                        self.stats['sources']['web_scraping'] += 1
                        self.discovered_documents.add(link)
                
                logger.info(f"Scraped {page_url}: found {len(doc_links)} document links")
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                logger.error(f"Error scraping {page_url}: {e}")
        
        logger.info(f"Found {len(documents)} documents via web scraping")
        return documents
    
    def extract_title_from_url(self, url: str) -> str:
        """Extract a title from a document URL."""
        filename = os.path.basename(urlparse(url).path)
        if filename:
            # Remove extension and clean up
            name = os.path.splitext(filename)[0]
            return name.replace('-', ' ').replace('_', ' ').title()
        return "Unknown Document"
    
    def guess_mime_type(self, url: str) -> str:
        """Guess MIME type from file extension."""
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        mime_map = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.csv': 'text/csv',
            '.txt': 'text/plain'
        }
        return mime_map.get(ext, 'application/octet-stream')
    
    def validate_and_quarantine_document(self, filepath: Path, document_info: Dict):
        """
        Validate a downloaded PDF document. If it's corrupted, move it to the quarantine directory.
        """
        if filepath.suffix.lower() != '.pdf':
            return  # Only validate PDFs for now

        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                if len(reader.pages) > 0:
                    return # File is valid
            # Also consider empty PDFs as potentially valid unless they raise an exception
            if PyPDF2.PdfReader(filepath).is_encrypted:
                 logging.warning(f"PDF is encrypted, cannot validate: {filepath}")
                 return

        except Exception as e:
            logger.error(f"Corrupted document detected: {filepath}. Reason: {e}")
            quarantine_path = self.quarantine_dir / filepath.name
            try:
                filepath.rename(quarantine_path)
                logger.info(f"Moved corrupted file to quarantine: {quarantine_path}")
                self.stats['quarantined_documents'] += 1
                self.stats['downloaded_documents'] -= 1 # It was counted as downloaded before validation
                # Log the source for further investigation
                logger.error(f"Corrupted file source URL: {document_info.get('source_url', 'Unknown')}")
            except OSError as move_error:
                logger.error(f"Failed to move corrupted file {filepath} to quarantine: {move_error}")

    def download_document(self, document_info: Dict) -> bool:
        """Download a document file, validate it, and place it in the correct directory."""
        if not self.download_files:
            return True
            
        try:
            source_url = document_info['source_url']
            if not source_url or source_url.lower() == 'none':
                raise ValueError("Missing or invalid source_url")

            generated_filename_with_path = self.generate_filename(document_info)
            base_filename = Path(generated_filename_with_path).name

            response = requests.get(source_url, timeout=60, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type')
            if content_type:
                document_info['mime_type'] = content_type
                extension = mimetypes.guess_extension(content_type)
                if extension and not base_filename.endswith(extension):
                    logger.warning(f"Correcting filename extension for {base_filename} to {extension} based on content type {content_type}")
                    base_filename = f"{Path(base_filename).stem}{extension}"

            file_extension = Path(base_filename).suffix.lower()
            
            if file_extension in self.image_extensions:
                filepath = self.images_dir / base_filename
            elif file_extension == '.html':
                filepath = self.content_dir / base_filename
            else:
                year_path = Path(generated_filename_with_path).parent
                filepath = self.documents_dir / year_path / base_filename

            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            if filepath.exists():
                logger.info(f"File already exists: {filepath}. Skipping download.")
                return True

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Successfully downloaded to {filepath}")
            self.stats['downloaded_documents'] += 1
            
            self.validate_and_quarantine_document(filepath, document_info)

            return True
            
        except Exception as e:
            logger.error(f"Failed to download {document_info.get('title', 'Unknown')} from {document_info.get('source_url', '')}: {e}")
            self.stats['failed_downloads'] += 1
            return False
    
    def generate_filename(self, document_info: Dict) -> str:
        """Generate a filename for the document."""
        title = document_info['title']
        date = document_info['date'][:4]  # Year
        mime_type = document_info['mime_type']
        
        # Get file extension
        extension = "pdf"  # default
        for doc_type, ext in self.document_types.items():
            if doc_type in mime_type:
                extension = ext
                break
        
        # Clean title for filename
        clean_title = re.sub(r'[^\w\s-]', '', title)
        clean_title = re.sub(r'[-\s]+', '-', clean_title).strip('-')
        
        return f"{date}/{clean_title}.{extension}"
    
    def update_statistics(self, document_info: Dict):
        """Update crawl statistics."""
        self.stats['total_documents'] += 1
        
        # Update source statistics
        source = document_info.get('source', 'unknown')
        if source not in self.stats['sources']:
            self.stats['sources'][source] = 0
        self.stats['sources'][source] += 1
        
        # Update MIME type statistics
        mime_type = document_info.get('mime_type', 'unknown')
        if mime_type not in self.stats['mime_types']:
            self.stats['mime_types'][mime_type] = 0
        self.stats['mime_types'][mime_type] += 1
    
    def save_metadata(self, documents: List[Dict]):
        """Save document metadata to JSON file."""
        metadata_file = self.metadata_dir / "documents_metadata.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved metadata for {len(documents)} documents to {metadata_file}")
    
    def save_summary(self):
        """Save crawler summary statistics."""
        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']
        self.stats['duration_seconds'] = duration.total_seconds()
        
        summary_file = self.output_dir / "crawl_summary.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, default=str)
        
        logger.info(f"Saved crawl summary to {summary_file}")
    
    def save_images_metadata(self):
        """Scan the images folder and save metadata for all images."""
        images_metadata = []
        images_dir = self.images_dir
        # Load document metadata for cross-referencing
        doc_meta_path = self.metadata_dir / "documents_metadata.json"
        doc_meta = []
        if doc_meta_path.exists():
            with open(doc_meta_path, 'r', encoding='utf-8') as f:
                try:
                    doc_meta = json.load(f)
                except Exception:
                    doc_meta = []
        doc_meta_by_filename = {Path(d['source_url']).name: d for d in doc_meta if d.get('source_url')}
        for img_file in images_dir.glob("*.jpg"):
            meta = {
                "filename": img_file.name,
                "relative_path": str(img_file.relative_to(self.output_dir)),
                "file_size": img_file.stat().st_size,
                "mime_type": "image/jpeg",
                "source_url": None,
                "title": None,
                "source": None
            }
            # Try to find source info from doc metadata
            doc_info = doc_meta_by_filename.get(img_file.name)
            if doc_info:
                meta["source_url"] = doc_info.get("source_url")
                meta["title"] = doc_info.get("title")
                meta["source"] = doc_info.get("source")
            images_metadata.append(meta)
        # Save metadata
        images_meta_path = self.metadata_dir / "images_metadata.json"
        with open(images_meta_path, 'w', encoding='utf-8') as f:
            json.dump(images_metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved metadata for {len(images_metadata)} images to {images_meta_path}")

    def crawl(self):
        """Main crawling method that fetches from all sources."""
        logger.info("Starting comprehensive NEFAC document crawl...")
        
        all_documents = []
        
        # 1. Fetch from WordPress REST API
        wp_media = self.fetch_wordpress_media()
        all_documents.extend(wp_media)
        
        # 2. Fetch from GraphQL API
        gql_media = self.fetch_graphql_media()
        all_documents.extend(gql_media)
        
        # 3. Fetch posts with full content (enhanced with Faust key)
        content_docs = self.fetch_posts_with_content()
        all_documents.extend(content_docs)
        
        # 4. Fetch posts with attachments
        post_attachments = self.fetch_posts_with_attachments()
        all_documents.extend(post_attachments)
        
        # 5. Fetch news posts with attachments
        news_attachments = self.fetch_news_with_attachments()
        all_documents.extend(news_attachments)
        
        # 6. Run link-scraper tool for additional discovery
        link_documents = self.run_link_scraper()
        for link in link_documents:
            if link not in self.discovered_documents:
                document_info = {
                    'id': f"link_{len(all_documents)}",
                    'title': self.extract_title_from_url(link),
                    'source_url': link,
                    'mime_type': self.guess_mime_type(link),
                    'date': datetime.now().isoformat(),
                    'modified': datetime.now().isoformat(),
                    'alt_text': '',
                    'description': f'Found via link-scraper tool',
                    'caption': '',
                    'source': 'link_discovery',
                    'file_size': 0
                }
                all_documents.append(document_info)
                self.stats['sources']['link_discovery'] += 1
                self.discovered_documents.add(link)
        
        # 7. Scrape web pages for additional documents
        web_documents = self.scrape_web_pages_for_documents()
        all_documents.extend(web_documents)
        
        # Remove duplicates based on source_url
        unique_documents = []
        seen_urls = set()
        
        for doc in all_documents:
            if doc['source_url'] not in seen_urls:
                unique_documents.append(doc)
                seen_urls.add(doc['source_url'])
        
        logger.info(f"Found {len(unique_documents)} unique documents")
        
        # Download documents and update statistics
        for doc in unique_documents:
            self.update_statistics(doc)
            
            if self.download_document(doc):
                self.stats['downloaded_documents'] += 1
            else:
                self.stats['failed_downloads'] += 1
        
        # Save metadata and summary
        self.save_metadata(unique_documents)
        self.save_images_metadata()
        self.save_summary()
        
        logger.info("Comprehensive crawl completed!")
        logger.info(f"Total documents found: {self.stats['total_documents']}")
        logger.info(f"Successfully downloaded: {self.stats['downloaded_documents']}")
        logger.info(f"Failed downloads: {self.stats['failed_downloads']}")
        logger.info(f"Quarantined (corrupted) documents: {self.stats['quarantined_documents']}")
        
        return unique_documents

def main():
    load_dotenv()  # Load environment variables from .env file
    
    parser = argparse.ArgumentParser(description="Comprehensive NEFAC document crawler with Faust authentication")
    parser.add_argument("--output-dir", default="nefac_documents", help="Output directory")
    parser.add_argument("--metadata-only", action="store_true", help="Only fetch metadata, don't download files")
    parser.add_argument("--document-types", nargs="+", help="Specific document types to fetch")
    parser.add_argument("--skip-web-scraping", action="store_true", help="Skip web scraping (API only)")
    parser.add_argument("--faust-key", help="Faust secret key for authenticated GraphQL access")
    
    args = parser.parse_args()
    
    # Use provided Faust key or try to get from environment
    faust_key = args.faust_key or os.getenv('FAUST_SECRET_KEY')
    
    if faust_key:
        logger.info("Using Faust secret key for enhanced GraphQL access")
    else:
        logger.warning("No Faust secret key provided - using public APIs only")
    
    crawler = NEFACDocumentCrawler(
        output_dir=args.output_dir,
        download_files=not args.metadata_only,
        faust_key=faust_key
    )
    
    if args.document_types:
        crawler.document_types = {k: v for k, v in crawler.document_types.items() 
                                if any(dt in k for dt in args.document_types)}
    
    documents = crawler.crawl()
    
    print(f"\nComprehensive crawl completed! Found {len(documents)} documents.")
    if faust_key:
        print("✅ Used Faust secret key for enhanced GraphQL access")
    else:
        print("⚠️  Used public APIs only (no Faust key provided)")
    print(f"Check the '{args.output_dir}' directory for results.")

if __name__ == "__main__":
    main() 