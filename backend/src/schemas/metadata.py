from __future__ import annotations

from dataclasses import field
from typing import ClassVar, any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseMetadata(BaseModel):

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="allow")
    id: int | str = Field(description="Unique identifier for the document")
    title: str = Field(min_length=1, description="Document title")
    filename: str = Field(min_length=1, description="Original filename")
    source_url: str = Field(description="Source URL of the document")
    date: str = Field(description="Document creation/publication date")
    modified: str | None = Field(default=None, description="Last modification date")
    mime_type: str | None = Field(default=None, description="MIME type of the document")
    file_size: int | None = Field(default=None, ge=0, description="File size in bytes")
    download_date: str | None = Field(default=None, description="Date when document was downloaded")
    crawler_version: str | None = Field(default=None, description="Version of crawler used")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("file://")):
            raise ValueError("source_url must be a valid URL")
        return v


class AuthorMetadata(BaseModel):

    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Author's full name")
    slug: str = Field(min_length=1, description="URL-friendly author identifier")
    uri: str = Field(description="Author's URI/profile link")
    description: str | None = Field(default=None, description="Author biography or description")
    email: str | None = Field(default=None, description="Author's email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class CategoryMetadata(BaseModel):
    name: str
    slug: str
    description: str | None = None
    count: int | None = None


class ContentMetadata(BaseMetadata):
    graphql_id: str | None = None
    slug: str
    file_path: str
    uri: str
    link: str
    source_url: str
    excerpt: str | None = None
    content_length: int | None = None
    author: AuthorMetadata | None = None
    categories: list[CategoryMetadata] | None = None
    tags: list[str] | None = None
    featured_image: object | None = None
    comment_count: int | None = None
    source: str | None = None
    file_size: int | None = None
    mime_type: str | None = None


class PDFMetadata(BaseMetadata):
    alt_text: str | None = None
    description: str | None = None
    caption: str | None = None
    source: str | None = None
    file_created: str | None = None
    file_modified: str | None = None
    file_path: str
    processing_timestamp: float | None = None
    http_status_code: int | None = None
    http_headers: dict[str, object] | None = None
    content_length_header: str | None = None
    last_modified_header: str | None = None
    etag_header: str | None = None
    server_header: str | None = None
    content_encoding: str | None = None
    content_disposition: str | None = None
    cache_control: str | None = None
    expires: str | None = None
    file_extension: str | None = None
    file_type_category: str | None = None
    is_image: bool | None = None
    is_document: bool | None = None
    is_archive: bool | None = None
    validation_status: str | None = None


class YouTubeMetadata(BaseModel):
    id: str
    title: str
    video_id: str
    source_url: str
    date: str
    modified: str | None = None
    description: str | None = None
    duration: int | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    uploader: str | None = None
    channel: str | None = None
    channel_id: str | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    thumbnail: str | None = None
    uploader_url: str | None = None
    availability: str | None = None
    live_status: str | None = None
    release_timestamp: str | None = None
    chapters: dict[str, any] | None = None
    heatmap: dict[str, any] | None = None
    transcript_available: bool | None = None
    transcript_file: str | None = None
    transcript_length: int | None = None
    transcript_word_count: int | None = None
    mime_type: str | None = None
    source: str | None = None
    download_date: str | None = None
    crawler_version: str | None = None
    file_size: int | None = None


class PDFChunkMetadata(PDFMetadata):
    page_number: int = 0  # Optional, for compatibility
    total_pages: int
    chunk_index: int
    total_chunks_in_page: int = 0  # Optional, for compatibility
    total_chunks_in_document: int = 0  # For document-level chunking
    chunking_strategy: str
    pages: list[int] = field(default_factory=list)  # List of page numbers this chunk covers
    pages_info: list[dict[str, any]] = field(default_factory=list)  # List of page info dicts for each page covered by the chunk


class ContentChunkMetadata(ContentMetadata):
    section_path: list[str]
    section_index: int
    chunk_index: int
    total_chunks_in_section: int
    chunking_strategy: str
    anchor: str | None = None
    html_url: str | None = None
    chunk_start: int | None = None
    chunk_end: int | None = None


class YouTubeChunkMetadata(YouTubeMetadata):
    chunk_index: int
    total_chunks_in_video: int
    chunking_strategy: str
    start_time: float = 0.0
    end_time: float = 0.0
