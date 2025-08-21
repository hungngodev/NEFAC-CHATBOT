"""
Downloaders Package for NEFAC Crawler

┌─────────────────────────────────────────────────────────────────────┐
│                      Download Pipeline                            │
│                                                                    │
│  DocumentDownloader ───► MetadataManager ───► Processors          │
│        │                      │                                      │
│        ▼                      ▼                                      │
│  File Download    Metadata Enrichment & Validation                 │
│                                                                    │
└─────────────────────────────────────────────────────────────────────┘

Components:
1. DocumentDownloader - Handles file downloads with retry logic and error handling
2. MetadataManager - Manages document metadata, validation, and enrichment

The downloaders package provides a robust pipeline for downloading documents
and managing their associated metadata throughout the crawling process.
"""

from .document_downloader import DocumentDownloader
from .metadata_manager import MetadataManager

__all__ = ["DocumentDownloader", "MetadataManager"]
