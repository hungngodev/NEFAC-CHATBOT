from __future__ import annotations

from dataclasses import field
from typing import Any, ClassVar

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
    expected_size: int | None = Field(default=None, ge=0, description="Expected file size in bytes from Content-Length")
    download_date: str | None = Field(default=None, description="Date when document was downloaded")
    crawler_version: str | None = Field(default=None, description="Version of crawler used")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        if v and not (v.startswith("http://") or v.startswith("https://") or v.startswith("file://")):
            raise ValueError("source_url must be a valid URL")
        return v


# General document metadata - alias for BaseMetadata
class DocumentMetadata(BaseMetadata):
    """General document metadata for all document types."""


class HTMLMetadata(BaseMetadata):
    """Metadata for HTML content from WordPress API."""

    slug: str = Field(description="URL-friendly identifier from WordPress")
    file_path: str = Field(description="Local file path where document is stored")
    uri: str = Field(description="URI path for the document")
    link: str = Field(description="WordPress link/permalink")
    excerpt: str | None = Field(default=None, description="Content excerpt from WordPress")
    source: str | None = Field(default=None, description="Source system or extraction method")
    status: str | None = Field(default=None, description="WordPress post status")
    content_type: str | None = Field(default=None, description="WordPress content type (post, page, etc.)")
    validation_status: str | None = Field(default=None, description="Validation status of the metadata")


class PDFMetadata(BaseMetadata):
    """Metadata for PDF documents from WordPress API."""

    alt_text: str | None = Field(default=None, description="Alternative text for the media")
    description: str | None = Field(default=None, description="Media description from WordPress")
    caption: str | None = Field(default=None, description="Media caption from WordPress")
    source: str | None = Field(default=None, description="Source system or extraction method")
    processing_timestamp: float | None = Field(default=None, description="Timestamp when document was processed")
    file_extension: str | None = Field(default=None, description="File extension (.pdf)")
    file_type_category: str | None = Field(default=None, description="Category of file type")
    is_document: bool | None = Field(default=None, description="Whether this is classified as a document")
    validation_status: str | None = Field(default=None, description="Validation status of the metadata")


class XLSXMetadata(BaseMetadata):
    """Metadata for Excel/spreadsheet documents from WordPress API."""

    alt_text: str | None = Field(default=None, description="Alternative text for the media")
    description: str | None = Field(default=None, description="Media description from WordPress")
    caption: str | None = Field(default=None, description="Media caption from WordPress")
    source: str | None = Field(default=None, description="Source system or extraction method")
    file_path: str = Field(description="Local file path where document is stored")
    processing_timestamp: float | None = Field(default=None, description="Timestamp when document was processed")
    file_extension: str | None = Field(default=None, description="File extension (.xlsx, .xls)")
    file_type_category: str | None = Field(default=None, description="Category of file type")
    is_document: bool | None = Field(default=None, description="Whether this is classified as a document")
    validation_status: str | None = Field(default=None, description="Validation status of the metadata")


class YouTubeMetadata(BaseMetadata):
    """Metadata for YouTube videos."""

    video_id: str = Field(description="YouTube video ID")
    description: str | None = Field(default=None, description="Video description")
    duration: int | None = Field(default=None, description="Video duration in seconds")
    view_count: int | None = Field(default=None, description="Number of views")
    like_count: int | None = Field(default=None, description="Number of likes")
    comment_count: int | None = Field(default=None, description="Number of comments")
    uploader: str | None = Field(default=None, description="Video uploader")
    channel: str | None = Field(default=None, description="Channel name")
    channel_id: str | None = Field(default=None, description="YouTube channel ID")
    tags: list[str] | None = Field(default=None, description="Video tags")
    categories: list[str] | None = Field(default=None, description="Video categories")
    thumbnail: str | None = Field(default=None, description="Thumbnail URL")
    uploader_url: str | None = Field(default=None, description="Uploader profile URL")
    availability: str | None = Field(default=None, description="Video availability status")
    live_status: str | None = Field(default=None, description="Live status")
    release_timestamp: str | None = Field(default=None, description="Original release timestamp")
    chapters: dict[str, Any] | None = Field(default=None, description="Video chapters")
    heatmap: dict[str, Any] | None = Field(default=None, description="Video heatmap data")
    transcript_available: bool | None = Field(default=None, description="Whether transcript is available")
    transcript_file: str | None = Field(default=None, description="Path to transcript file")
    transcript_length: int | None = Field(default=None, description="Transcript length in characters")
    transcript_word_count: int | None = Field(default=None, description="Number of words in transcript")
    source: str | None = Field(default=None, description="Source system or extraction method")


# Shared chunk info for all chunked metadata types
class ChunkInfo(BaseModel):
    chunk_index: int
    chunking_strategy: str


class PDFChunkMetadata(ChunkInfo, PDFMetadata):
    page_number: int = 0  # for compatibility
    total_pages: int
    total_chunks_in_page: int = 0  # for compatibility
    total_chunks_in_document: int = 0  # For document-level chunking
    pages: list[int] = field(default_factory=list)  # List of page numbers this chunk covers
    pages_info: list[dict[str, Any]] = field(default_factory=list)  # List of page info dicts for each page covered by the chunk


class HTMLChunkMetadata(ChunkInfo, HTMLMetadata):
    section_path: list[str]
    section_index: int
    total_chunks_in_section: int
    anchor: str | None = None
    html_url: str | None = None
    chunk_start: int | None = None
    chunk_end: int | None = None


class XLSXChunkMetadata(ChunkInfo, XLSXMetadata):
    sheet_name: str | None = None
    total_sheets: int = 0
    total_chunks_in_sheet: int = 0
    total_chunks_in_document: int = 0
    row_start: int | None = None
    row_end: int | None = None
    column_start: str | None = None
    column_end: str | None = None


class YouTubeChunkMetadata(ChunkInfo, YouTubeMetadata):
    total_chunks_in_video: int
    start_time: float = 0.0
    end_time: float = 0.0
