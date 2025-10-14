"""Native LlamaIndex document loaders replacing Unstructured.io.

Supports multiple document types with fallback to Unstructured.
Based on: https://developers.llamaindex.ai/python/framework/llama_cloud/llama_parse/
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

from llama_index.core import Document as LIDocument
from llama_index.core import SimpleDirectoryReader

from src.service.ingestion_service.loader.spreadsheet_utils import (
    process_xlsx_intelligently,
)

logger = logging.getLogger(__name__)


class UnifiedDocumentLoader:
    """Unified document loader using native LlamaIndex readers.
    
    Supports:
    - PDF (LlamaParse or PyMuPDF)
    - HTML (BeautifulSoup)
    - DOCX/PPTX (python-docx/python-pptx)
    - XLSX (pandas with intelligent processing)
    - YouTube (youtube-transcript-api)
    - Fallback to Unstructured.io
    """
    
    def __init__(
        self,
        use_llamaparse: bool = None,
        llamaparse_api_key: Optional[str] = None,
        fallback_to_unstructured: bool = True,
    ):
        """Initialize the unified loader.
        
        Args:
            use_llamaparse: Use LlamaParse for PDFs (premium)
            llamaparse_api_key: API key for LlamaParse
            fallback_to_unstructured: Fall back to Unstructured.io if reader fails
        """
        self.use_llamaparse = use_llamaparse if use_llamaparse is not None else os.getenv("USE_LLAMAPARSE", "false").lower() in {"true", "1", "yes"}
        self.llamaparse_api_key = llamaparse_api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self.fallback_to_unstructured = fallback_to_unstructured
        
        self._readers_cache = {}
    
    def _dependency_hint(self, package: str, install_hint: Optional[str] = None) -> None:
        hint = install_hint or f"pip install {package}"
        logger.debug("Dependency '%s' missing. Install via: %s", package, hint)

    def _get_pdf_reader(self):
        """Get PDF reader (LlamaParse or PyMuPDF)."""
        if self.use_llamaparse and self.llamaparse_api_key:
            try:
                from llama_parse import LlamaParse
                
                if "llamaparse" not in self._readers_cache:
                    self._readers_cache["llamaparse"] = LlamaParse(
                        api_key=self.llamaparse_api_key,
                        result_type="markdown",  # or "text"
                        verbose=True,
                        language="en",
                    )
                    logger.info("Using LlamaParse for PDF parsing")
                
                return self._readers_cache["llamaparse"]
            except ImportError:
                logger.warning("llama-parse not installed, falling back to PyMuPDF")
                self._dependency_hint("llama-parse")
        
        # Fallback to PyMuPDF
        try:
            from llama_index.readers.file import PyMuPDFReader
            
            if "pymupdf" not in self._readers_cache:
                self._readers_cache["pymupdf"] = PyMuPDFReader()
                logger.info("Using PyMuPDF for PDF parsing")
            
            return self._readers_cache["pymupdf"]
        except ImportError:
            logger.warning("PyMuPDFReader not available")
            self._dependency_hint("pymupdf")
            return None
    
    def _get_html_reader(self):
        """Get HTML reader."""
        try:
            from llama_index.readers.web import BeautifulSoupWebReader  # type: ignore[import-not-found]
            
            if "html" not in self._readers_cache:
                self._readers_cache["html"] = BeautifulSoupWebReader()
                logger.info("Using BeautifulSoupWebReader for HTML parsing")
            
            return self._readers_cache["html"]
        except ImportError:
            logger.warning("BeautifulSoupWebReader not available")
            self._dependency_hint("beautifulsoup4")
            return None
    
    def _get_docx_reader(self):
        """Get DOCX reader."""
        try:
            from llama_index.readers.file import DocxReader
            
            if "docx" not in self._readers_cache:
                self._readers_cache["docx"] = DocxReader()
                logger.info("Using DocxReader for DOCX parsing")
            
            return self._readers_cache["docx"]
        except ImportError:
            logger.warning("DocxReader not available")
            self._dependency_hint("python-docx")
            return None
    
    def _load_excel_intelligently(
        self,
        file_path: Path,
        extra_info: Optional[dict] = None
    ) -> List[LIDocument]:
        """Load Excel with intelligent table processing (preserves structure)."""
        try:
            import pandas as pd  # noqa: F401

            logger.info("Using spreadsheet utils for XLSX conversion")
            chunks = process_xlsx_intelligently(str(file_path), extra_info or {})

            docs: List[LIDocument] = []
            for text, chunk_meta in chunks:
                doc_meta = (extra_info or {}).copy()
                doc_meta.update(chunk_meta)
                docs.append(LIDocument(text=text, metadata=doc_meta))

            return docs
        except ImportError:
            logger.warning("pandas not installed; falling back to Unstructured for spreadsheets")
            self._dependency_hint("pandas")
            return self._fallback_unstructured(file_path, extra_info)
        except Exception as e:
            logger.error("Failed to load Excel file: %s", e)
            return []
    
    def _get_youtube_reader(self):
        """Get YouTube transcript reader."""
        try:
            from llama_index.readers.youtube_transcript import YoutubeTranscriptReader  # type: ignore[import-not-found]
            
            if "youtube" not in self._readers_cache:
                self._readers_cache["youtube"] = YoutubeTranscriptReader()
                logger.info("Using YoutubeTranscriptReader for YouTube videos")
            
            return self._readers_cache["youtube"]
        except ImportError:
            logger.warning("YoutubeTranscriptReader not available")
            self._dependency_hint("youtube-transcript-api")
            return None
    
    def _fallback_unstructured(
        self, 
        file_path: Union[str, Path],
        extra_info: Optional[dict] = None
    ) -> List[LIDocument]:
        """Fallback to Unstructured.io loader."""
        try:
            from llama_index.readers.file import UnstructuredReader

            logger.warning("Falling back to UnstructuredReader for %s", file_path)
            reader = UnstructuredReader()
            docs = reader.load_data(file=str(file_path), extra_info=extra_info)
            return docs
        except ImportError:
            logger.error("UnstructuredReader not installed; install 'unstructured' extras")
            self._dependency_hint("unstructured", "pip install unstructured[all-docs]")
            raise
        except Exception as e:
            logger.error("Unstructured fallback failed: %s", e)
            raise
    
    def load_file(
        self,
        file_path: Union[str, Path],
        extra_info: Optional[dict] = None,
    ) -> List[LIDocument]:
        """Load a file using appropriate LlamaIndex reader.
        
        Args:
            file_path: Path to file
            extra_info: Additional metadata
            
        Returns:
            List of LlamaIndex documents
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        logger.info(f"Loading {file_path.name} with LlamaIndex")
        
        try:
            docs = []
            
            # Route to appropriate reader
            if suffix == ".pdf":
                reader = self._get_pdf_reader()
                if reader:
                    docs = reader.load_data(file_path)
            
            elif suffix in [".html", ".htm"]:
                reader = self._get_html_reader()
                if reader:
                    # BeautifulSoupWebReader expects URLs, use file:// scheme
                    docs = reader.load_data(urls=[f"file://{file_path.absolute()}"])
            
            elif suffix == ".docx":
                reader = self._get_docx_reader()
                if reader:
                    docs = reader.load_data(file_path)
            
            elif suffix in [".xlsx", ".xls", ".csv"]:
                # Use intelligent Excel processor
                docs = self._load_excel_intelligently(file_path, extra_info)
            
            else:
                # Try generic SimpleDirectoryReader
                logger.info(f"Using SimpleDirectoryReader for {suffix}")
                try:
                    reader = SimpleDirectoryReader(input_files=[str(file_path)])
                    docs = reader.load_data()
                except Exception as exc:
                    logger.warning("SimpleDirectoryReader failed: %s", exc)
                    docs = []
            
            # If no docs loaded, try fallback
            if not docs and self.fallback_to_unstructured:
                logger.warning(f"No docs loaded with native readers, trying fallback")
                docs = self._fallback_unstructured(file_path, extra_info)
            
            # Add extra metadata
            if extra_info and docs:
                for doc in docs:
                    doc.metadata.update(extra_info)
            
            logger.info(f"Loaded {len(docs)} documents from {file_path.name} using LlamaIndex")
            return docs
        
        except Exception as e:
            logger.error(f"LlamaIndex reader failed for {file_path}: {e}")
            
            if self.fallback_to_unstructured:
                return self._fallback_unstructured(file_path, extra_info)
            else:
                raise
    
    def load_youtube(
        self,
        video_url: str,
        extra_info: Optional[dict] = None,
    ) -> List[LIDocument]:
        """Load YouTube video transcript.
        
        Args:
            video_url: YouTube video URL or video ID
            extra_info: Additional metadata
            
        Returns:
            List of LlamaIndex documents
        """
        try:
            reader = self._get_youtube_reader()
            if not reader:
                raise ImportError("YouTube reader not available")
            
            docs = reader.load_data(ytlinks=[video_url])
            
            if extra_info:
                for doc in docs:
                    doc.metadata.update(extra_info)
            
            logger.info(f"Loaded YouTube transcript from {video_url}")
            return docs
        
        except Exception as e:
            logger.error(f"Failed to load YouTube transcript: {e}")
            
            if self.fallback_to_unstructured:
                # Try existing YouTube loader
                try:
                    from src.service.ingestion_service.loader.unstructured_loader import unstructured_loader
                    
                    nodes = unstructured_loader(video_url, extra_info or {})
                    docs = [LIDocument(text=node.get_content(), metadata=node.metadata) for node in nodes]
                    return docs
                except:
                    raise e
            else:
                raise
    
    def load_text(
        self,
        text: str,
        extra_info: Optional[dict] = None,
    ) -> List[LIDocument]:
        """Load raw text as document.
        
        Args:
            text: Raw text content
            extra_info: Additional metadata
            
        Returns:
            List containing single LlamaIndex document
        """
        metadata = extra_info or {}
        doc = LIDocument(text=text, metadata=metadata)
        return [doc]
