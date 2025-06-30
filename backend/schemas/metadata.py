from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


# Base schema for shared/common fields
class BaseMetadata(BaseModel):
    id: Union[int, str]
    title: str
    filename: str
    source_url: str
    date: str
    modified: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    download_date: Optional[str] = None
    crawler_version: Optional[str] = None


# HTML/Content metadata
class AuthorMetadata(BaseModel):
    name: str
    slug: str
    uri: str
    description: Optional[str] = None


class CategoryMetadata(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    count: Optional[int] = None


class ContentMetadata(BaseMetadata):
    graphql_id: Optional[str] = None
    slug: str
    file_path: str
    uri: str
    link: str
    source_url: str
    excerpt: Optional[str] = None
    content_length: Optional[int] = None
    author: Optional[AuthorMetadata] = None
    categories: Optional[List[CategoryMetadata]] = None
    tags: Optional[List[str]] = None
    featured_image: Optional[Any] = None
    comment_count: Optional[int] = None
    source: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    # ... add any other fields present in the metadata


# PDF/Document metadata
class PDFMetadata(BaseMetadata):
    alt_text: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    source: Optional[str] = None
    file_created: Optional[str] = None
    file_modified: Optional[str] = None
    file_path: str
    processing_timestamp: Optional[float] = None
    http_status_code: Optional[int] = None
    http_headers: Optional[Dict[str, Any]] = None
    content_length_header: Optional[str] = None
    last_modified_header: Optional[str] = None
    etag_header: Optional[str] = None
    server_header: Optional[str] = None
    content_encoding: Optional[str] = None
    content_disposition: Optional[str] = None
    cache_control: Optional[str] = None
    expires: Optional[str] = None
    file_extension: Optional[str] = None
    file_type_category: Optional[str] = None
    is_image: Optional[bool] = None
    is_document: Optional[bool] = None
    is_archive: Optional[bool] = None
    validation_status: Optional[str] = None
    # ... add any other fields present in the metadata


# YouTube metadata
class YouTubeMetadata(BaseModel):
    id: str
    title: str
    video_id: str
    source_url: str
    date: str
    modified: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    uploader: Optional[str] = None
    channel: Optional[str] = None
    channel_id: Optional[str] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    thumbnail: Optional[str] = None
    uploader_url: Optional[str] = None
    availability: Optional[str] = None
    live_status: Optional[str] = None
    release_timestamp: Optional[str] = None
    chapters: Optional[Any] = None
    heatmap: Optional[Any] = None
    transcript_available: Optional[bool] = None
    transcript_file: Optional[str] = None
    transcript_length: Optional[int] = None
    transcript_word_count: Optional[int] = None
    mime_type: Optional[str] = None
    source: Optional[str] = None
    download_date: Optional[str] = None
    crawler_version: Optional[str] = None
    file_size: Optional[int] = None
    # ... add any other fields present in the metadata


class PDFChunkMetadata(PDFMetadata):
    page_number: int = 0  # Optional, for compatibility
    total_pages: int
    chunk_index: int
    total_chunks_in_page: int = 0  # Optional, for compatibility
    total_chunks_in_document: int = 0  # For document-level chunking
    chunking_strategy: str
    pages: list = []  # List of page numbers this chunk covers
    pages_info: list = []  # List of page info dicts for each page covered by the chunk
    # ... add any other fields present in the metadata


class ContentChunkMetadata(ContentMetadata):
    section_path: list
    section_index: int
    chunk_index: int
    total_chunks_in_section: int
    chunking_strategy: str
    anchor: Optional[str] = None
    html_url: Optional[str] = None
    chunk_start: Optional[int] = None
    chunk_end: Optional[int] = None


class YouTubeChunkMetadata(YouTubeMetadata):
    chunk_index: int
    total_chunks_in_video: int
    chunking_strategy: str
    start_time: float = 0.0
    end_time: float = 0.0
