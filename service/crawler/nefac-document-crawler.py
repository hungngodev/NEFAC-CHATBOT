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

4. YouTube Channel Crawling:
   - Crawls NEFAC YouTube channel for all videos
   - Extracts transcripts, metadata, and video information
   - Organizes content in youtube/ folder
   - Comprehensive metadata following existing schema

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
- YouTube channel crawling with transcript extraction
"""

import os
import json
import requests
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin, parse_qs
from pathlib import Path
import argparse
from typing import List, Dict, Any, Optional
import logging
import re
import subprocess
import sys
import mimetypes
from dotenv import load_dotenv
import random
try:
    import PyPDF2
except ImportError:
    print("PyPDF2 is not installed. Please install it with: pip install PyPDF2")
    sys.exit(1)

# YouTube-specific imports
yt_dlp = None
YouTubeTranscriptApi = None
WebshareProxyConfig = None
try:
    import yt_dlp
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    from youtube_transcript_api.proxies import WebshareProxyConfig
    import json
    import tempfile
except ImportError:
    print("YouTube dependencies not installed. Please install with: pip install yt-dlp youtube-transcript-api")

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

from service.schemas.metadata import PDFMetadata, ContentMetadata, YouTubeMetadata

class NEFACDocumentCrawler:
    def __init__(self, output_dir: str = "nefac_documents", download_files: bool = True, faust_key: Optional[str] = None, youtube_delay: float = 10.0, webshare_username: Optional[str] = None, webshare_password: Optional[str] = None):
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
                "content_extraction": 0,
                "selenium_scraper": 0,
                "youtube_channel": 0
            },
            "start_time": datetime.now(),
            "end_time": None,
            "mime_types": {}
        }
        
        # Track discovered documents to avoid duplicates
        self.discovered_documents = set()
        
        # YouTube channel configuration
        self.youtube_channel_url = "https://www.youtube.com/@nefac"
        self.youtube_dir = self.output_dir / "youtube"
        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        self.youtube_delay = youtube_delay
        self.webshare_username = webshare_username
        self.webshare_password = webshare_password
        
    def normalize_transcript(self, transcript):
        """Normalize transcript entries to consistent dictionary format"""
        normalized = []
        for entry in transcript:
            if hasattr(entry, 'text'):
                # Convert object to dict
                normalized.append({
                    'text': entry.text,
                    'start': entry.start,
                    'duration': entry.duration
                })
            elif isinstance(entry, dict):
                # Already a dict, keep as is
                normalized.append(entry)
        return normalized
    
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
        
        # Fetch all media items -
        media_items = self.fetch_with_pagination(self.endpoints["media"], params={'per_page': 100})
        
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
                            uri
                            description
                        }
                    }
                    categories {
                        nodes {
                            name
                            slug
                            description
                            count
                        }
                    }
                    tags {
                        nodes {
                            name
                            slug
                            description
                            count
                        }
                    }
                    uri
                    link
                    commentCount
                    featuredImage {
                        node {
                            id
                            databaseId
                            title
                            altText
                            sourceUrl
                            mediaDetails {
                                width
                                height
                                sizes {
                                    name
                                    sourceUrl
                                    width
                                    height
                                }
                            }
                        }
                    }
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
                if not response or 'data' not in response or not response['data'].get('posts'):
                    logger.error(f"Invalid or empty GraphQL response for posts: {response}")
                    break
                    
                data = response['data']['posts']
                posts = data.get('nodes', [])
                page_info = data.get('pageInfo', {})
                
                if not posts:
                    logger.info("No posts returned in this page, ending fetch.")
                    break

                all_posts.extend(posts)
                
                has_next_page = page_info.get('hasNextPage', False)
                after_cursor = page_info.get('endCursor')
                
                logger.info(f"Fetched {len(posts)} posts (total: {len(all_posts)}), hasNextPage: {has_next_page}")
                
            except Exception as e:
                logger.error(f"Error fetching posts: {e}")
                break
        
        logger.info(f"Total posts fetched: {len(all_posts)}")
        
        documents_found = []
        content_metadata = []
        
        for post in all_posts:
            try:
                post_id = post.get('databaseId')
                if not post_id:
                    logger.warning(f"Skipping post with no databaseId: {post.get('title')}")
                    continue

                title = post.get('title', 'Untitled')
                slug = post.get('slug')
                
                # Correctly generate a flat filename for HTML content files
                if title and title != "Untitled":
                    clean_title = re.sub(r'[^\w\s-]', '', title).strip()
                    filename = f"{re.sub(r'\s+', '_', clean_title)[:100]}.html"
                elif slug:
                    filename = f"{slug}.html"
                else:
                    filename = f"post_{post_id}.html"

                filepath = self.content_dir / filename
                
                html_content = post.get('content')
                if not html_content:
                    html_content = ""
                    logger.warning(f"Post {post_id} has no content.")

                featured_image_info = None
                if post.get('featuredImage') and post['featuredImage'].get('node'):
                    img_node = post['featuredImage']['node']
                    featured_image_info = {
                        "id": img_node.get('databaseId'),
                        "title": img_node.get('title'),
                        "alt_text": img_node.get('altText'),
                        "source_url": img_node.get('sourceUrl'),
                        "width": img_node.get('mediaDetails', {}).get('width'),
                        "height": img_node.get('mediaDetails', {}).get('height'),
                        "sizes": img_node.get('mediaDetails', {}).get('sizes', [])
                    }
                
                author_node = post.get('author', {}).get('node', {})
                content_meta = {
                    "id": post_id,
                    "graphql_id": post.get('id'),
                    "title": title,
                    "slug": slug,
                    "filename": filename,
                    "file_path": str(filepath.relative_to(self.output_dir)),
                    "date": post.get('date'),
                    "modified": post.get('modified'),
                    "uri": post.get('uri'),
                    "link": post.get('link'),
                    "source_url": f"https://nefac.org{post.get('uri')}" if post.get('uri') else post.get('link'),
                    "excerpt": post.get('excerpt'),
                    "content_length": len(html_content),
                    "author": {
                        "name": author_node.get('name'),
                        "slug": author_node.get('slug'),
                        "uri": author_node.get('uri'),
                        "description": author_node.get('description')
                    },
                    "categories": post.get('categories', {}).get('nodes', []),
                    "tags": post.get('tags', {}).get('nodes', []),
                    "featured_image": featured_image_info,
                    "comment_count": post.get('commentCount', 0),
                    "mime_type": "text/html",
                    "source": "graphql_content",
                    "download_date": datetime.now().isoformat(),
                    "crawler_version": "2.0",
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                content_meta['file_size'] = filepath.stat().st_size
                content_metadata.append(content_meta)

                links = self.extract_documents_from_content(html_content)
                if links:
                    logger.info(f"Found {len(links)} document links in post {post_id}")
                    for link in links:
                        document_info = {
                            'id': f"content-{post_id}-{os.path.basename(link)}",
                            'title': self.extract_title_from_url(link),
                            'source_url': link,
                            'mime_type': self.guess_mime_type(link),
                            'date': post.get('date'),
                            'modified': post.get('modified'),
                            'source': 'content_extraction',
                            'description': f"Extracted from post: {title}",
                        }
                        documents_found.append(document_info)
                        self.stats['sources']['content_extraction'] += 1
                        
            except Exception as e:
                logger.error(f"Error processing post {post.get('databaseId')}: {e}", exc_info=True)
                
        content_metadata_file = self.metadata_dir / "content_metadata.json"
        try:
            with open(content_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(content_metadata, f, indent=2, default=str)
            logger.info(f"Saved metadata for {len(content_metadata)} content files to {content_metadata_file}")
        except Exception as e:
            logger.error(f"Error saving content metadata: {e}")

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
        
        # Run link-scraper tool if available
        link_scraper_path = Path("../tools/link-scraper/main.py")
        if link_scraper_path.exists():
            logger.info("Running link-scraper tool to discover document links...")
            try:
                result = subprocess.run(
                    [sys.executable, str(link_scraper_path), self.base_url, "--max-depth", "4", "--verbose", "--include-attachments", "--output", "link_discovery_results.json"],
                    capture_output=True,
                    text=True,
                    cwd=self.output_dir
                )
                if result.returncode == 0:
                    logger.info("Link-scraper tool completed successfully")
                    
                    # Parse the JSON output to extract document links
                    output_file = self.output_dir / "link_discovery_results.json"
                    if output_file.exists():
                        with open(output_file, 'r', encoding='utf-8') as f:
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
                    logger.warning(f"Link-scraper tool failed: {result.stderr}")
                    return []
            except Exception as e:
                logger.error(f"Error running link-scraper tool: {e}")
                return []
        else:
            logger.warning(f"Link-scraper tool not found at {link_scraper_path}")
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

            # Add comprehensive file system metadata
            stat = filepath.stat()
            document_info.update({
                'file_size': stat.st_size,
                'file_created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'file_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'file_path': str(filepath.relative_to(self.output_dir)),
                'filename': base_filename,
                'download_date': datetime.now().isoformat(),
                'processing_timestamp': datetime.now().timestamp(),
                'crawler_version': '2.0',
                'http_status_code': response.status_code,
                'http_headers': dict(response.headers),
                'content_length_header': response.headers.get('content-length'),
                'last_modified_header': response.headers.get('last-modified'),
                'etag_header': response.headers.get('etag'),
                'server_header': response.headers.get('server'),
                'content_encoding': response.headers.get('content-encoding'),
                'content_disposition': response.headers.get('content-disposition'),
                'cache_control': response.headers.get('cache-control'),
                'expires': response.headers.get('expires'),
                'file_extension': file_extension,
                'file_type_category': self.get_file_type_category(file_extension),
                'is_image': file_extension in self.image_extensions,
                'is_document': file_extension in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.txt'],
                'is_archive': file_extension in ['.zip', '.rar', '.7z', '.tar', '.gz'],
                'validation_status': 'pending'
            })

            logger.info(f"Successfully downloaded to {filepath}")
            self.stats['downloaded_documents'] += 1
            
            self.validate_and_quarantine_document(filepath, document_info)

            return True
            
        except Exception as e:
            logger.error(f"Failed to download {document_info.get('title', 'Unknown')} from {document_info.get('source_url', '')}: {e}")
            self.stats['failed_downloads'] += 1
            return False
    
    def get_file_type_category(self, extension: str) -> str:
        """Categorize file types."""
        if extension in self.image_extensions:
            return 'image'
        elif extension in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.txt']:
            return 'document'
        elif extension in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return 'archive'
        elif extension in ['.html', '.htm']:
            return 'web_page'
        else:
            return 'other'
    
    def generate_filename(self, document_info: Dict) -> str:
        """Generate a meaningful filename for the document."""
        title = document_info.get('title', 'Unknown Document')
        date = document_info.get('date', '')
        mime_type = document_info.get('mime_type', '')
        source = document_info.get('source', 'unknown')
        
        # Extract year from date
        year = "unknown"
        if date and len(date) >= 4:
            year = date[:4]
        
        # Get file extension
        extension = "pdf"  # default
        for doc_type, ext in self.document_types.items():
            if doc_type in mime_type:
                extension = ext
                break
        
        # If we have a URL, try to get extension from it
        source_url = document_info.get('source_url', '')
        if source_url:
            url_ext = Path(urlparse(source_url).path).suffix.lower()
            if url_ext and url_ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.txt', '.jpg', '.jpeg', '.png', '.gif']:
                extension = url_ext[1:]  # Remove the dot
        
        # Clean title for filename
        if title and title != "Unknown Document":
            # Remove special characters but keep spaces and hyphens
            clean_title = re.sub(r'[^\w\s\-_.]', '', title)
            # Replace multiple spaces/hyphens with single
            clean_title = re.sub(r'[-\s]+', '-', clean_title)
            # Remove leading/trailing hyphens
            clean_title = clean_title.strip('-')
            # Limit length
            clean_title = clean_title[:80]
        else:
            # Generate title from source URL if available
            if source_url:
                parsed_url = urlparse(source_url)
                path_parts = parsed_url.path.strip('/').split('/')
                if path_parts and path_parts[-1]:
                    clean_title = Path(path_parts[-1]).stem
                    clean_title = re.sub(r'[^\w\s\-_.]', '', clean_title)
                    clean_title = re.sub(r'[-\s]+', '-', clean_title)
                    clean_title = clean_title.strip('-')[:80]
                else:
                    clean_title = f"document_{source.replace('_', '-')}"
            else:
                clean_title = f"document_{source.replace('_', '-')}"
        
        # Add source identifier if it's not a standard source
        if source not in ['wordpress_rest_api', 'graphql_api', 'graphql_authenticated']:
            clean_title = f"{clean_title}_{source.replace('_', '-')}"
        
        # Ensure we have a valid filename
        if not clean_title or clean_title == '':
            clean_title = f"document_{year}"
        
        return f"{year}/{clean_title}.{extension}"
    
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
        self.stats["mime_types"][mime_type] = self.stats["mime_types"].get(mime_type, 0) + 1
    
    def save_metadata(self, documents: List[Dict]):
        """
        Save validated document metadata to JSON file. Only valid entries are written.
        """
        valid_documents = []
        for entry in documents:
            # Determine type by mime_type or file extension
            mime_type = entry.get('mime_type', '')
            ext = entry.get('file_extension', '')
            try:
                if mime_type == 'application/pdf' or ext == '.pdf':
                    validated = PDFMetadata(**entry)
                elif mime_type == 'text/html' or ext == '.html':
                    validated = ContentMetadata(**entry)
                else:
                    # Default to PDFMetadata for unknown types (or raise error)
                    validated = PDFMetadata(**entry)
                valid_documents.append(validated.dict())
            except Exception as e:
                logger.error(f"Schema validation failed for metadata entry: {e}. Skipping entry: {entry}")
        if not valid_documents:
            logger.warning("No valid metadata entries to save.")
            return
        # Save to JSON file (determine file by type)
        if valid_documents and 'mime_type' in valid_documents[0] and valid_documents[0]['mime_type'] == 'text/html':
            out_path = self.metadata_dir / 'content_metadata.json'
        else:
            out_path = self.metadata_dir / 'documents_metadata.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(valid_documents, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(valid_documents)} metadata entries to {out_path}")

    def save_summary(self):
        """Save crawl statistics to a summary file."""
        summary_file = self.output_dir / "crawl_summary.json"
        self.stats['end_time'] = datetime.now()
        self.stats['duration_seconds'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        # Convert start_time and end_time to strings for JSON serialization
        summary_data = self.stats.copy()
        summary_data['start_time'] = summary_data['start_time'].isoformat()
        summary_data['end_time'] = summary_data['end_time'].isoformat()
        
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2, default=str)
            
    def save_images_metadata(self):
        """Scan images folder and generate comprehensive metadata."""
        logger.info("Generating metadata for all images...")
        images_metadata_file = self.metadata_dir / "images_metadata.json"
        all_images_metadata = []

        # Load document metadata to find matches
        documents_metadata_file = self.metadata_dir / "documents_metadata.json"
        doc_metadata = []
        if documents_metadata_file.exists():
            with open(documents_metadata_file, 'r') as f:
                try:
                    doc_metadata = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Could not parse documents_metadata.json")

        # Create a lookup table from source_url to metadata
        metadata_lookup = {item['source_url']: item for item in doc_metadata if 'source_url' in item}

        # Scan the images directory
        for image_file in self.images_dir.glob('**/*'):
            if image_file.is_file():
                # Basic file info
                file_info = {
                    "filename": image_file.name,
                    "file_path": str(image_file.relative_to(self.output_dir)),
                    "file_size": image_file.stat().st_size,
                    "file_extension": image_file.suffix,
                    "file_created": datetime.fromtimestamp(image_file.stat().st_ctime).isoformat(),
                    "file_modified": datetime.fromtimestamp(image_file.stat().st_mtime).isoformat()
                }

                # Find a matching record in the downloaded metadata
                # This is tricky because we don't have a direct URL mapping
                # We can try to match by filename, but it's not foolproof
                
                # Heuristic: try to reconstruct a possible source_url
                # This is a guess and may not be accurate
                potential_url_path = f"/wp-content/uploads/{image_file.name}"
                potential_url = urljoin(self.base_url, potential_url_path)

                matched_meta = metadata_lookup.get(potential_url)

                if matched_meta:
                    # Merge metadata
                    full_meta = {**matched_meta, **file_info}
                    full_meta['metadata_source'] = 'merged_from_documents_metadata'
                else:
                    # Create a basic record
                    full_meta = file_info
                    full_meta['title'] = image_file.stem
                    full_meta['source_url'] = None # We don't know the original URL
                    full_meta['metadata_source'] = 'generated_from_filesystem'

                all_images_metadata.append(full_meta)

        with open(images_metadata_file, 'w') as f:
            json.dump(all_images_metadata, f, indent=2)
            
        logger.info(f"Saved metadata for {len(all_images_metadata)} images.")

    def download_html_pages_from_links(self) -> List[Dict]:
        """Download HTML content from all discovered URLs using link-scraper results."""
        logger.info("Downloading HTML content from discovered links...")
        link_results_path = self.output_dir / "link_discovery_results.json"
        html_pages_metadata = []

        if not link_results_path.exists():
            logger.warning("Link discovery results not found. Run link-scraper first.")
            return []

        with open(link_results_path, 'r') as f:
            try:
                link_data = json.load(f)
                urls_to_scrape = link_data.get("urls", [])
            except json.JSONDecodeError:
                logger.error("Could not parse link_discovery_results.json")
                return []
        
        logger.info(f"Found {len(urls_to_scrape)} URLs to scrape from link discovery results.")
        
        for url in urls_to_scrape:
            try:
                if self.is_document_url(url) or urlparse(url).path.startswith('/wp-content/uploads/'):
                    logger.info(f"Skipping document/media URL: {url}")
                    continue

                response = requests.get(url, timeout=20)
                response.raise_for_status()

                html_content = response.text
                
                # Generate a meaningful filename
                page_title = self.extract_title_from_html(html_content)
                if not page_title:
                    page_title = self.extract_title_from_url(url)
                
                filename_info = {'title': page_title, 'source_url': url}
                filename = self.generate_filename(filename_info)
                
                filepath = self.content_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                page_meta = {
                    "source_url": url,
                    "title": page_title,
                    "filename": filename,
                    "file_path": str(filepath.relative_to(self.output_dir)),
                    "file_size": filepath.stat().st_size,
                    "download_date": datetime.now().isoformat(),
                    "source": "link_scraper",
                    "http_status_code": response.status_code,
                    "content_type": response.headers.get('Content-Type')
                }
                html_pages_metadata.append(page_meta)
                
                logger.info(f"Saved HTML from {url} to {filepath}")
                time.sleep(0.5)

            except requests.RequestException as e:
                logger.error(f"Failed to download HTML from {url}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while processing {url}: {e}")

        # Save metadata
        html_metadata_file = self.metadata_dir / "html_pages_metadata.json"
        with open(html_metadata_file, 'w') as f:
            json.dump(html_pages_metadata, f, indent=2)
            
        logger.info(f"Saved metadata for {len(html_pages_metadata)} HTML pages.")
        
        return html_pages_metadata

    def extract_title_from_html(self, html_content: str) -> str:
        """Extract title from HTML content."""
        try:
            # Simple regex to extract title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # Clean up the title
                title = re.sub(r'\s+', ' ', title)  # Replace multiple spaces
                return title
        except Exception:
            pass
        return "Untitled"

    def run_selenium_scraper(self):
        """Run the Selenium-based scraper to extract text content from web pages."""
        selenium_scraper_path = Path("tools/selenium-scraper/nefac_scraper.py")
        if not selenium_scraper_path.exists():
            logger.warning(f"Selenium scraper not found at {selenium_scraper_path}")
            return []
        
        logger.info("Running Selenium scraper for text content extraction...")
        
        try:
            # Run the Selenium scraper
            result = subprocess.run(
                [sys.executable, str(selenium_scraper_path)],
                capture_output=True,
                text=True,
                cwd=self.output_dir,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("Selenium scraper completed successfully")
                
                # Run cleanup to remove error pages
                cleanup_path = Path("tools/selenium-scraper/cleanup.py")
                if cleanup_path.exists():
                    logger.info("Running cleanup to remove error pages...")
                    subprocess.run(
                        [sys.executable, str(cleanup_path)],
                        cwd=self.output_dir
                    )
                
                # Process the extracted text files
                return self.process_selenium_output()
            else:
                logger.warning(f"Selenium scraper failed: {result.stderr}")
                return []
                
        except subprocess.TimeoutExpired:
            logger.warning("Selenium scraper timed out")
            return []
        except Exception as e:
            logger.error(f"Error running Selenium scraper: {e}")
            return []

    def process_selenium_output(self):
        """Process the output from the Selenium scraper."""
        output_dir = self.output_dir / "output"
        if not output_dir.exists():
            return []
        
        processed_files = []
        
        for txt_file in output_dir.glob("*.txt"):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract URL from the first line
                lines = content.split('\n')
                if lines and lines[0].startswith('Source URL: '):
                    url = lines[0].replace('Source URL: ', '')
                    text_content = '\n'.join(lines[2:])  # Skip URL line and empty line
                else:
                    url = str(txt_file.stem)
                    text_content = content
                
                # Create metadata for the text file
                metadata = {
                    'url': url,
                    'filename': txt_file.name,
                    'content_type': 'text_content',
                    'source': 'selenium_scraper',
                    'extracted_at': datetime.now().isoformat(),
                    'file_size': txt_file.stat().st_size,
                    'word_count': len(text_content.split())
                }
                
                # Move file to content directory with better naming
                safe_name = self.generate_filename({'title': url.replace('https://www.nefac.org', '').strip('/')})
                if not safe_name or safe_name == "Untitled":
                    safe_name = txt_file.stem
                
                new_filename = f"{safe_name}.txt"
                new_path = self.output_dir / "content" / new_filename
                
                # Ensure content directory exists
                new_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move and rename the file
                txt_file.rename(new_path)
                
                processed_files.append({
                    'url': url,
                    'title': safe_name,
                    'extracted_at': metadata['extracted_at'],
                    'file_size': metadata['file_size'],
                    'word_count': metadata['word_count'],
                    'new_path': str(new_path)
                })
                
                logger.info(f"Processed Selenium output: {new_filename}")
                
            except Exception as e:
                logger.error(f"Error processing Selenium output file {txt_file}: {e}")
        
        # Save metadata for Selenium content
        if processed_files:
            selenium_metadata = {
                'source': 'selenium_scraper',
                'extracted_at': datetime.now().isoformat(),
                'total_files': len(processed_files),
                'files': processed_files
            }
            
            metadata_file = self.output_dir / "metadata" / "selenium_content_metadata.json"
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(selenium_metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved Selenium content metadata: {len(processed_files)} files")
        
        return processed_files

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        try:
            parsed_url = urlparse(url)
            if parsed_url.hostname in ["youtu.be"]:
                return parsed_url.path[1:]
            elif parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
                if parsed_url.path == "/watch":
                    return parse_qs(parsed_url.query)["v"][0]
                elif parsed_url.path.startswith("/embed/"):
                    return parsed_url.path.split("/")[2]
                elif parsed_url.path.startswith("/v/"):
                    return parsed_url.path.split("/")[2]
            return None
        except Exception:
            return None
    
    def get_youtube_transcript(self, video_id: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """Get transcript for a YouTube video using multiple free methods"""
        if not YouTubeTranscriptApi and not yt_dlp:
            logger.warning("YouTube dependencies not available")
            return None
            
        # Method 1: YouTube Transcript API (Primary method - most reliable)
        if YouTubeTranscriptApi:
            transcript = self._get_transcript_youtube_api(video_id, max_retries)
            if transcript:
                logger.info(f"Transcript found using YouTube Transcript API for {video_id}")
                return transcript
        
        # Method 2: yt-dlp subtitle extraction (Secondary method)
        if yt_dlp:
            transcript = self._get_transcript_ytdlp(video_id)
            if transcript:
                logger.info(f"Transcript found using yt-dlp for {video_id}")
                return transcript
        
        # Method 3: YouTube's internal API endpoints
        transcript = self._get_transcript_alternative_methods(video_id)
        if transcript:
            logger.info(f"Transcript found using YouTube internal API for {video_id}")
            return transcript
        
        # Method 4: Free online transcript services (Fallback)
        transcript = self._get_transcript_online_services(video_id)
        if transcript:
            logger.info(f"Transcript found using online services for {video_id}")
            return transcript
        
        logger.warning(f"No transcript found for video {video_id} using any method")
        return None
    
    def _get_transcript_youtube_api(self, video_id: str, max_retries: int = 3) -> Optional[List[Dict]]:
        """Get transcript using YouTube Transcript API (primary method)"""
        # Initialize the API client
        ytt_api = None
        if self.webshare_username and self.webshare_password:
            logger.info("Using Webshare proxy for YouTube requests.")
            try:
                ytt_api = YouTubeTranscriptApi(  # type: ignore
                    proxy_config=WebshareProxyConfig(  # type: ignore
                        proxy_username=self.webshare_username,
                        proxy_password=self.webshare_password,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to initialize Webshare proxy: {e}")
                # Fallback to a direct client
                ytt_api = YouTubeTranscriptApi()  # type: ignore
        else:
            ytt_api = YouTubeTranscriptApi()  # type: ignore
        
        # Language preferences in order of preference
        language_preferences = ["en", "en-US", "en-GB", "en-orig"]
        
        for attempt in range(max_retries):
            try:
                # Add small delay between attempts to avoid rate limiting
                if attempt > 0:
                    delay = random.uniform(1, 3) * attempt
                    logger.info(f"Retrying transcript fetch after {delay:.1f}s delay (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                
                # Get available transcripts
                transcript_list = ytt_api.list_transcripts(video_id)
                
                # Try preferred languages first
                for lang in language_preferences:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        transcript_data = transcript.fetch()
                        return list(transcript_data)  # type: ignore
                    except Exception as e:
                        if "no element found" not in str(e).lower():
                            continue  # Try next language
                        else:
                            raise e  # Propagate XML parsing errors for retry
                
                # If no preferred language found, try manual transcripts first
                try:
                    for transcript in transcript_list:
                        if not transcript.is_generated:  # Manual transcripts
                            transcript_data = transcript.fetch()
                            return list(transcript_data)  # type: ignore
                except Exception as e:
                    if "no element found" not in str(e).lower():
                        pass  # Continue to auto-generated
                    else:
                        raise e  # Propagate XML parsing errors for retry
                
                # Finally try any auto-generated transcript
                try:
                    for transcript in transcript_list:
                        if transcript.is_generated:  # Auto-generated transcripts
                            transcript_data = transcript.fetch()
                            return list(transcript_data)  # type: ignore
                except Exception as e:
                    if "no element found" not in str(e).lower():
                        pass
                    else:
                        raise e  # Propagate XML parsing errors for retry
                
                return None
                
            except Exception as e:
                error_msg = str(e).lower()
                if "disabled" in error_msg:
                    return None
                elif "unavailable" in error_msg:
                    return None
                elif "private" in error_msg:
                    return None
                elif "no element found" in error_msg and attempt < max_retries - 1:
                    logger.warning(f"XML parsing error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    continue  # Retry for XML parsing errors
                elif attempt == max_retries - 1:
                    logger.error(f"Transcript error after {max_retries} attempts: {str(e)}")
                    return None
        
        return None
    
    def _get_transcript_ytdlp(self, video_id: str) -> Optional[List[Dict]]:
        """Get transcript using yt-dlp subtitle extraction"""
        if not yt_dlp:
            return None
            
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Try multiple language preferences
        language_preferences = [
            ["en"],  # English first
            ["en-US"],  # US English
            ["en-GB"],  # UK English
            ["en-orig"],  # Original English
        ]
        
        for lang_pref in language_preferences:
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    ydl_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "skip_download": True,
                        "writeautomaticsub": True,
                        "subtitleslangs": lang_pref,
                        "subtitlesformat": "json3",  # JSON format for easier parsing
                        "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
                    }

                    if self.webshare_username and self.webshare_password:
                        proxy_url = f"http://{self.webshare_username}:{self.webshare_password}@p.webshare.io:8080"
                        ydl_opts['proxy'] = proxy_url
                        logger.info("Using Webshare proxy for yt-dlp requests.")

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])

                        # Look for subtitle files
                        subtitle_files = list(Path(temp_dir).glob(f"{video_id}.*.json3"))
                        if not subtitle_files:
                            continue  # Try next language preference
                        
                        # Read and parse the JSON subtitle file
                        with open(subtitle_files[0], "r", encoding="utf-8") as f:
                            subtitle_data = json.load(f)

                        # Convert to transcript format
                        transcript_entries = []
                        for event in subtitle_data.get("events", []):
                            if "segs" in event:
                                # Combine all segments in this event
                                text = "".join(seg.get("utf8", "") for seg in event["segs"])
                                if text.strip():
                                    transcript_entries.append(
                                        {
                                            "text": text.strip(),
                                            "start": event.get("tStartMs", 0) / 1000.0,  # Convert to seconds
                                            "duration": event.get("dDurationMs", 0) / 1000.0,
                                        }
                                    )
                        
                        if transcript_entries:
                            logger.info(f"Successfully extracted transcript using yt-dlp for {video_id} with lang {lang_pref}")
                            return self.normalize_transcript(transcript_entries)

            except Exception as e:
                logger.debug(f"yt-dlp extraction with lang {lang_pref} failed: {str(e)}")
                continue  # Try next language preference
        
        logger.warning(f"yt-dlp could not extract transcript for {video_id} with any language preference.")
        return None
    
    def _get_transcript_online_services(self, video_id: str) -> Optional[List[Dict]]:
        """Get transcript using free online services"""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # List of free transcript services to try
        services = [
            {
                "name": "YouTube Transcript API (alternative)",
                "url": f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en",
                "method": "xml"
            },
            {
                "name": "DownSub",
                "url": f"https://downsub.com/?url={video_url}",
                "method": "scrape"
            },
            {
                "name": "YouTube Transcript",
                "url": f"https://youtubetranscript.com/?v={video_id}",
                "method": "scrape"
            },
            {
                "name": "SaveFrom",
                "url": f"https://en.savefrom.net/{video_url}",
                "method": "scrape"
            },
            {
                "name": "YouTube Transcript Finder",
                "url": f"https://transcript.yt/{video_id}",
                "method": "scrape"
            }
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        for service in services:
            try:
                logger.debug(f"Trying {service['name']} for video {video_id}")
                response = requests.get(service['url'], timeout=15, headers=headers)
                
                if response.status_code == 200:
                    content = response.text
                    
                    if service['method'] == 'xml':
                        # Parse XML transcript data
                        transcript = self._parse_xml_transcript(content)
                        if transcript:
                            logger.info(f"Found transcript using {service['name']}")
                            return transcript
                    
                    elif service['method'] == 'scrape':
                        # Try to extract transcript from HTML content
                        transcript = self._parse_html_transcript(content, video_id)
                        if transcript:
                            logger.info(f"Found transcript using {service['name']}")
                            return transcript
                            
            except Exception as e:
                logger.debug(f"Service {service['name']} failed: {str(e)}")
                continue
        
        # Method: Try scraping from YouTube's embedded player
        try:
            embed_url = f"https://www.youtube.com/embed/{video_id}"
            response = requests.get(embed_url, timeout=10, headers=headers)
            
            if response.status_code == 200:
                content = response.text
                transcript = self._parse_html_transcript(content, video_id)
                if transcript:
                    logger.info(f"Found transcript in embedded player for {video_id}")
                    return transcript
        except Exception as e:
            logger.debug(f"Embedded player scraping failed: {str(e)}")
        
        return None
    
    def _parse_xml_transcript(self, xml_content: str) -> Optional[List[Dict]]:
        """Parse XML transcript data"""
        try:
            from xml.etree import ElementTree
            root = ElementTree.fromstring(xml_content)
            transcript_entries = []
            
            for text_element in root.findall('.//text'):
                start = float(text_element.get('start', 0))
                duration = float(text_element.get('dur', 0))
                text = text_element.text or ""
                
                if text.strip():
                    transcript_entries.append({
                        "text": text.strip(),
                        "start": start,
                        "duration": duration
                    })
            
            return transcript_entries if transcript_entries else None
        except Exception as e:
            logger.debug(f"XML parsing failed: {str(e)}")
            return None
    
    def _parse_html_transcript(self, html_content: str, video_id: str) -> Optional[List[Dict]]:
        """Parse transcript data from HTML content"""
        try:
            # Look for common transcript patterns in HTML
            import re
            
            # Pattern 1: Look for transcript text in common formats
            patterns = [
                r'<div[^>]*class="[^"]*transcript[^"]*"[^>]*>(.*?)</div>',
                r'<span[^>]*class="[^"]*caption[^"]*"[^>]*>(.*?)</span>',
                r'<p[^>]*class="[^"]*subtitle[^"]*"[^>]*>(.*?)</p>',
                r'data-text="([^"]*)"',
                r'data-transcript="([^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if matches:
                    # Clean up the found text
                    cleaned_text = []
                    for match in matches:
                        # Remove HTML tags
                        clean_text = re.sub(r'<[^>]+>', '', match)
                        clean_text = re.sub(r'&[^;]+;', ' ', clean_text)  # Remove HTML entities
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()  # Normalize whitespace
                        
                        if clean_text and len(clean_text) > 10:  # Minimum meaningful text
                            cleaned_text.append(clean_text)
                    
                    if cleaned_text:
                        # Create transcript entries with estimated timing
                        transcript_entries = []
                        for i, text in enumerate(cleaned_text):
                            transcript_entries.append({
                                "text": text,
                                "start": i * 5.0,  # Estimate 5 seconds per entry
                                "duration": 5.0
                            })
                        return transcript_entries
            
            # Pattern 2: Look for JSON transcript data
            json_patterns = [
                r'window\.__INITIAL_DATA__\s*=\s*({.*?});',
                r'ytInitialData\s*=\s*({.*?});',
                r'"transcript":\s*(\[.*?\])',
                r'"captions":\s*(\[.*?\])',
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, list):
                            # Direct transcript array
                            return self._parse_json_transcript(data)
                        elif isinstance(data, dict):
                            # Look for transcript in nested structure
                            transcript = self._find_transcript_in_json(data)
                            if transcript:
                                return transcript
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            logger.debug(f"HTML parsing failed: {str(e)}")
            return None
    
    def _parse_json_transcript(self, data: List[Dict]) -> Optional[List[Dict]]:
        """Parse transcript data from JSON structure"""
        try:
            transcript_entries = []
            
            for item in data:
                if isinstance(item, dict):
                    text = item.get('text', '') or item.get('content', '') or item.get('caption', '')
                    start = item.get('start', 0) or item.get('time', 0) or item.get('timestamp', 0)
                    duration = item.get('duration', 0) or item.get('dur', 0)
                    
                    if text and isinstance(text, str) and text.strip():
                        transcript_entries.append({
                            "text": text.strip(),
                            "start": float(start) if start else 0,
                            "duration": float(duration) if duration else 0
                        })
            
            return transcript_entries if transcript_entries else None
            
        except Exception as e:
            logger.debug(f"JSON transcript parsing failed: {str(e)}")
            return None
    
    def _find_transcript_in_json(self, data: Dict) -> Optional[List[Dict]]:
        """Recursively search for transcript data in JSON structure"""
        try:
            # Common keys that might contain transcript data
            transcript_keys = ['transcript', 'captions', 'subtitles', 'text', 'content']
            
            for key in transcript_keys:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        return self._parse_json_transcript(value)
                    elif isinstance(value, dict):
                        result = self._find_transcript_in_json(value)
                        if result:
                            return result
            
            # Recursively search nested objects
            for key, value in data.items():
                if isinstance(value, dict):
                    result = self._find_transcript_in_json(value)
                    if result:
                        return result
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    for item in value:
                        result = self._find_transcript_in_json(item)
                        if result:
                            return result
            
            return None
            
        except Exception as e:
            logger.debug(f"JSON search failed: {str(e)}")
            return None
    
    def _get_transcript_alternative_methods(self, video_id: str) -> Optional[List[Dict]]:
        """Additional alternative methods for transcript extraction"""
        # Method: Try using YouTube's internal API endpoints
        try:
            # YouTube's internal transcript endpoint (may not always work)
            transcript_url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en"
            response = requests.get(transcript_url, timeout=10)
            
            if response.status_code == 200 and response.text.strip():
                # Parse XML transcript data
                from xml.etree import ElementTree
                try:
                    root = ElementTree.fromstring(response.text)
                    transcript_entries = []
                    
                    for text_element in root.findall('.//text'):
                        start = float(text_element.get('start', 0))
                        duration = float(text_element.get('dur', 0))
                        text = text_element.text or ""
                        
                        if text.strip():
                            transcript_entries.append({
                                "text": text.strip(),
                                "start": start,
                                "duration": duration
                            })
                    
                    if transcript_entries:
                        return transcript_entries
                except Exception as e:
                    logger.debug(f"XML parsing failed: {str(e)}")
        except Exception as e:
            logger.debug(f"Alternative transcript method failed: {str(e)}")
        
        return None
    
    def get_youtube_metadata(self, url: str) -> Dict[str, Any]:
        """Get comprehensive YouTube video metadata using yt-dlp"""
        if not yt_dlp:
            logger.warning("yt-dlp not available")
            return {"title": "Title not found"}
            
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    return {"title": "Title not found"}
                
                metadata = {
                    "title": info.get("title", "Title not found"),
                    "description": info.get("description", ""),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "upload_date": info.get("upload_date", ""),
                    "uploader": info.get("uploader", ""),
                    "channel": info.get("channel", ""),
                    "channel_id": info.get("channel_id", ""),
                    "tags": info.get("tags", []),
                    "categories": info.get("categories", []),
                    "language": info.get("language", ""),
                    "subtitles_available": bool(info.get("automatic_captions", {})),
                    "like_count": info.get("like_count", 0),
                    "age_limit": info.get("age_limit", 0),
                    "video_id": info.get("id", ""),
                    "webpage_url": info.get("webpage_url", url),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader_url": info.get("uploader_url", ""),
                    "channel_url": info.get("channel_url", ""),
                    "availability": info.get("availability", ""),
                    "live_status": info.get("live_status", ""),
                    "release_timestamp": info.get("release_timestamp", ""),
                    "comment_count": info.get("comment_count", 0),
                    "chapters": info.get("chapters", []),
                    "heatmap": info.get("heatmap", {}),
                }
                return metadata
        except Exception as e:
            logger.error(f"Error fetching metadata for {url}: {str(e)}")
            return {"title": "Title not found"}
    
    def save_youtube_transcript(self, video_id: str, transcript_data: List[Dict], metadata: Dict[str, Any]) -> str:
        """Save transcript data to file and return file path"""
        # Create filename from title
        title = metadata.get("title", "Unknown")
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        
        # Add video ID to ensure uniqueness
        filename = f"{safe_title}_{video_id}.txt"
        filepath = self.youtube_dir / filename
        
        # Save transcript as text
        with open(filepath, 'w', encoding='utf-8') as f:
            for entry in transcript_data:
                start_time = entry.get("start", 0)
                text = entry.get("text", "")
                f.write(f"[{start_time:.2f}s] {text}\n")
        
        return str(filepath)
    
    def crawl_youtube_channel(self) -> List[Dict]:
        """Crawl NEFAC YouTube channel for all videos"""
        if not yt_dlp:
            logger.warning("yt-dlp not available, skipping YouTube crawl")
            return []
            
        logger.info("Starting YouTube channel crawl...")
        
        # Get channel videos
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "playlist_items": "1-1000",  # Get up to 1000 videos
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract channel info
                channel_info = ydl.extract_info(self.youtube_channel_url, download=False)
                
                if not channel_info or 'entries' not in channel_info:
                    logger.error("Could not extract channel videos")
                    return []
                
                videos = channel_info['entries']
                logger.info(f"Found {len(videos)} videos in channel")
                
                youtube_documents = []
                
                for i, video in enumerate(videos, 1):
                    if not video:
                        continue
                        
                    video_url = video.get('url', '')
                    if not video_url:
                        continue
                    
                    logger.info(f"Processing video {i}/{len(videos)}: {video.get('title', 'Unknown')}")
                    
                    try:
                        # Get full metadata
                        full_metadata = self.get_youtube_metadata(video_url)
                        video_id = full_metadata.get("video_id", "")
                        
                        if not video_id:
                            logger.warning(f"Could not get video ID for {video_url}")
                            continue
                        
                        # Get transcript
                        transcript_data = self.get_youtube_transcript(video_id)
                        
                        # Normalize transcript data to consistent format
                        if transcript_data:
                            transcript_data = self.normalize_transcript(transcript_data)
                        
                        # Create document info
                        document_info = {
                            'id': f"youtube_{video_id}",
                            'title': full_metadata.get("title", "Unknown"),
                            'source_url': video_url,
                            'mime_type': 'text/plain',
                            'date': full_metadata.get("upload_date", ""),
                            'modified': full_metadata.get("upload_date", ""),
                            'alt_text': '',
                            'description': full_metadata.get("description", ""),
                            'caption': '',
                            'source': 'youtube_channel',
                            'file_size': 0,
                            'youtube_metadata': full_metadata,
                            'transcript_available': transcript_data is not None,
                            'video_id': video_id,
                            'channel': full_metadata.get("channel", ""),
                            'channel_id': full_metadata.get("channel_id", ""),
                            'duration': full_metadata.get("duration", 0),
                            'view_count': full_metadata.get("view_count", 0),
                            'like_count': full_metadata.get("like_count", 0),
                            'comment_count': full_metadata.get("comment_count", 0),
                            'tags': full_metadata.get("tags", []),
                            'categories': full_metadata.get("categories", []),
                            'thumbnail': full_metadata.get("thumbnail", ""),
                            'uploader': full_metadata.get("uploader", ""),
                            'uploader_url': full_metadata.get("uploader_url", ""),
                            'availability': full_metadata.get("availability", ""),
                            'live_status': full_metadata.get("live_status", ""),
                            'release_timestamp': full_metadata.get("release_timestamp", ""),
                            'chapters': full_metadata.get("chapters", []),
                            'heatmap': full_metadata.get("heatmap", {}),
                        }
                        
                        # Save transcript if available
                        if transcript_data:
                            transcript_file = self.save_youtube_transcript(video_id, transcript_data, full_metadata)
                            document_info['transcript_file'] = transcript_file
                            document_info['transcript_length'] = len(transcript_data)
                            
                            # Calculate transcript word count
                            total_words = sum(len(entry.get("text", "").split()) for entry in transcript_data)
                            document_info['transcript_word_count'] = total_words
                        
                        youtube_documents.append(document_info)
                        self.stats['sources']['youtube_channel'] += 1
                        
                        # Be respectful to YouTube servers
                        # Use a randomized delay to appear more human
                        delay = random.uniform(self.youtube_delay, self.youtube_delay + 5.0)
                        logger.info(f"Waiting for {delay:.2f} seconds before next video...")
                        time.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Error processing video {video_url}: {e}")
                        # Optional: Add a longer delay on error
                        time.sleep(self.youtube_delay * 2)
                        continue
                
                logger.info(f"Successfully processed {len(youtube_documents)} YouTube videos")
                return youtube_documents
                
        except Exception as e:
            logger.error(f"Error crawling YouTube channel: {e}")
            return []
    
    def save_youtube_metadata(self, youtube_documents: List[Dict]):
        """
        Save validated YouTube metadata to JSON file. Only valid entries are written.
        """
        valid_documents = []
        for entry in youtube_documents:
            try:
                validated = YouTubeMetadata(**entry)
                valid_documents.append(validated.dict())
            except Exception as e:
                logger.error(f"Schema validation failed for YouTube metadata entry: {e}. Skipping entry: {entry}")
        if not valid_documents:
            logger.warning("No valid YouTube metadata entries to save.")
            return
        out_path = self.metadata_dir / 'youtube_metadata.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(valid_documents, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(valid_documents)} YouTube metadata entries to {out_path}")

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
                    'description': 'Found via link-scraper tool',
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
        
        # 8. Download HTML pages from discovered URLs
        html_pages_metadata = self.download_html_pages_from_links()
        all_documents.extend(html_pages_metadata)
        
        # 9. Run Selenium scraper for text content extraction
        try:
            selenium_documents = self.run_selenium_scraper()
            for doc in selenium_documents:
                document_info = {
                    'id': f"selenium_{len(all_documents)}",
                    'title': doc.get('title', 'Unknown'),
                    'source_url': doc.get('url', ''),
                    'mime_type': 'text/plain',
                    'date': doc.get('extracted_at', datetime.now().isoformat()),
                    'modified': doc.get('extracted_at', datetime.now().isoformat()),
                    'alt_text': '',
                    'description': 'Found via Selenium scraper',
                    'caption': '',
                    'source': 'selenium_scraper',
                    'file_size': doc.get('file_size', 0),
                    'word_count': doc.get('word_count', 0)
                }
                all_documents.append(document_info)
                self.stats['sources']['selenium_scraper'] += 1
        except Exception as e:
            logger.error(f"Error in Selenium scraper: {e}")
            logger.info("Continuing with other sources...")
        
        # 10. Crawl YouTube channel
        youtube_documents = self.crawl_youtube_channel()
        all_documents.extend(youtube_documents)
        
        # Remove duplicates based on source_url
        unique_documents = []
        seen_urls = set()
        
        for doc in all_documents:
            source_url = doc.get('source_url', '')
            if source_url not in seen_urls:
                unique_documents.append(doc)
                seen_urls.add(source_url)
        
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
        self.save_youtube_metadata(youtube_documents)
        
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
    parser.add_argument("--youtube-only", action="store_true", help="Only crawl the NEFAC YouTube channel and save transcripts/metadata")
    parser.add_argument("--delay", type=float, default=10.0, help="Base delay in seconds between YouTube requests to avoid rate limiting.")
    parser.add_argument("--webshare-username", help="Webshare proxy username.")
    parser.add_argument("--webshare-password", help="Webshare proxy password.")
    
    args = parser.parse_args()
    
    # Use provided Faust key or try to get from environment
    faust_key = args.faust_key or os.getenv('FAUST_SECRET_KEY')
    webshare_username = args.webshare_username or os.getenv('WEBSHARE_USERNAME')
    webshare_password = args.webshare_password or os.getenv('WEBSHARE_PASSWORD')

    if faust_key:
        logger.info("Using Faust secret key for enhanced GraphQL access")
    else:
        logger.warning("No Faust secret key provided - using public APIs only")
    
    crawler = NEFACDocumentCrawler(
        output_dir=args.output_dir,
        download_files=not args.metadata_only,
        faust_key=faust_key,
        youtube_delay=args.delay,
        webshare_username=webshare_username,
        webshare_password=webshare_password
    )
    
    if args.document_types:
        crawler.document_types = {k: v for k, v in crawler.document_types.items() 
                                if any(dt in k for dt in args.document_types)}
    
    if args.youtube_only:
        crawler = NEFACDocumentCrawler(
            output_dir=args.output_dir,
            download_files=not args.metadata_only,
            faust_key=faust_key,
            youtube_delay=args.delay,
            webshare_username=webshare_username,
            webshare_password=webshare_password
        )
        # Set the correct NEFAC channel URL
        crawler.youtube_channel_url = "https://www.youtube.com/@nefac"
        youtube_documents = crawler.crawl_youtube_channel()
        crawler.save_youtube_metadata(youtube_documents)
        print(f"\nYouTube crawl completed! Found {len(youtube_documents)} videos.")
        print(f"Check the '{args.output_dir}/youtube' and '{args.output_dir}/metadata/youtube_metadata.json' for results.")
        return
    
    documents = crawler.crawl()
    
    print(f"\nComprehensive crawl completed! Found {len(documents)} documents.")
    if faust_key:
        print("✅ Used Faust secret key for enhanced GraphQL access")
    else:
        print("⚠️  Used public APIs only (no Faust key provided)")
    print(f"Check the '{args.output_dir}' directory for results.")

if __name__ == "__main__":
    main() 