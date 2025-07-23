"""
Downloaders package for NEFAC crawler.

This package contains downloaders and metadata managers.
"""

from .document_downloader import DocumentDownloader
from .metadata_manager import MetadataManager

__all__ = ["DocumentDownloader", "MetadataManager"]
