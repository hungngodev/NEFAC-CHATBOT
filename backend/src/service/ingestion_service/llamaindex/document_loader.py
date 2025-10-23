"""Native LlamaIndex document loaders replacing Unstructured.io.

Supports multiple document types with fallback to Unstructured.
Based on: https://developers.llamaindex.ai/python/framework/llama_cloud/llama_parse/
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Union
from urllib.parse import parse_qs, urlparse

from llama_index.core import Document as LIDocument
from llama_index.core import SimpleDirectoryReader

from src.service.ingestion_service.loader.spreadsheet_utils import (
    process_xlsx_intelligently,
)

logger = logging.getLogger(__name__)


class UnifiedDocumentLoader:
    @staticmethod
    def _extract_youtube_video_id(video_url: str) -> str:
        parsed = urlparse(video_url)

        if parsed.hostname in {"youtu.be", "www.youtu.be"}:
            return parsed.path.lstrip("/")

        if parsed.hostname and "youtube" in parsed.hostname:
            if parsed.path.startswith("/watch"):
                params = parse_qs(parsed.query)
                if "v" in params and params["v"]:
                    return params["v"][0]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/", 2)[2]
            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/", 2)[2]

        return video_url

    def _load_youtube_fallback(
        self,
        video_url: str,
        extra_info: Optional[dict] = None,
    ) -> List[LIDocument]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            logger.error("YouTube transcript fallback unavailable: %s", exc)
            raise

        video_id = self._extract_youtube_video_id(video_url)

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as exc:  # pragma: no cover - external service
            logger.error("Failed to fetch YouTube transcript via fallback: %s", exc)
            raise

        lines = []
        for chunk in transcript:
            text = str(chunk.get("text", "")).strip()
            if not text:
                continue

            start = chunk.get("start")
            duration = chunk.get("duration")
            if isinstance(start, (int, float)) and isinstance(duration, (int, float)):
                end = start + duration
                lines.append(f"[{start:.1f}s-{end:.1f}s] {text}")
            else:
                lines.append(text)

        if not lines:
            raise RuntimeError("YouTube transcript is empty")

        metadata = dict(extra_info or {})
        metadata.setdefault("source", video_url)
        metadata.setdefault("document_type", "youtube_transcript")

        document_text = "\n".join(lines)
        return [LIDocument(text=document_text, metadata=metadata)]

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
        llamaparse_auto_mode: Optional[bool] = None,
        llamaparse_extract_charts: Optional[bool] = None,
        llamaparse_result_type: Optional[str] = None,
        llamaparse_target_pages: Optional[str] = None,
        llamaparse_bbox_top: Optional[int] = None,
        llamaparse_bbox_bottom: Optional[int] = None,
        llamaparse_user_prompt: Optional[str] = None,
        llamaparse_invalidate_cache: bool = False,
        llamaparse_language: str = "en",
        llamaparse_skip_diagonal_text: bool = False,
        llamaparse_do_not_unroll_columns: bool = False,
        fallback_to_unstructured: bool = True,
    ):
        """Initialize the unified loader.

        Args:
            use_llamaparse: Use LlamaParse for PDFs (premium)
            llamaparse_api_key: API key for LlamaParse
            llamaparse_auto_mode: Enable automatic parser mode selection
            llamaparse_extract_charts: Extract tables/charts when supported
            llamaparse_result_type: Result format for parsed output
            llamaparse_target_pages: Parse specific pages (e.g., "1-5,7,10-15")
            llamaparse_bbox_top: Filter top N pixels (header removal)
            llamaparse_bbox_bottom: Filter bottom N pixels (footer removal)
            llamaparse_user_prompt: Custom parsing instructions
            llamaparse_invalidate_cache: Force re-parse cached documents
            llamaparse_language: Document language code (default: en)
            llamaparse_skip_diagonal_text: Skip text at diagonal angles
            llamaparse_do_not_unroll_columns: Keep multi-column layout
            fallback_to_unstructured: Fall back to Unstructured.io if reader fails
        """
        self.use_llamaparse = use_llamaparse if use_llamaparse is not None else os.getenv("USE_LLAMAPARSE", "false").lower() in {"true", "1", "yes"}
        self.llamaparse_api_key = llamaparse_api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self.llamaparse_auto_mode = llamaparse_auto_mode
        self.llamaparse_extract_charts = llamaparse_extract_charts
        self.llamaparse_result_type = llamaparse_result_type or "markdown"
        self.llamaparse_target_pages = llamaparse_target_pages
        self.llamaparse_bbox_top = llamaparse_bbox_top
        self.llamaparse_bbox_bottom = llamaparse_bbox_bottom
        self.llamaparse_user_prompt = llamaparse_user_prompt
        self.llamaparse_invalidate_cache = llamaparse_invalidate_cache
        self.llamaparse_language = llamaparse_language
        self.llamaparse_skip_diagonal_text = llamaparse_skip_diagonal_text
        self.llamaparse_do_not_unroll_columns = llamaparse_do_not_unroll_columns
        self.fallback_to_unstructured = fallback_to_unstructured

        self._readers_cache = {}

    def _dependency_hint(self, package: str, install_hint: Optional[str] = None) -> None:
        hint = install_hint or f"pip install {package}"
        logger.debug("Dependency '%s' missing. Install via: %s", package, hint)

    def _get_pdf_reader(self):
        """Get PDF reader (LlamaParse or PyMuPDF).

        Enhanced with all LlamaParse options from tutorial:
        https://developers.llamaindex.ai/python/framework/llama_cloud/llama_parse/
        """
        if self.use_llamaparse and self.llamaparse_api_key:
            try:
                from llama_parse import LlamaParse

                if "llamaparse" not in self._readers_cache:
                    # Build kwargs for LlamaParse with all advanced options
                    parser_kwargs = {
                        "api_key": self.llamaparse_api_key,
                        "result_type": self.llamaparse_result_type,
                        "verbose": True,
                        "language": self.llamaparse_language,
                        "invalidate_cache": self.llamaparse_invalidate_cache,
                    }

                    # Add optional parameters if specified
                    if self.llamaparse_auto_mode is not None:
                        parser_kwargs["auto_mode"] = self.llamaparse_auto_mode
                    if self.llamaparse_extract_charts is not None:
                        parser_kwargs["extract_charts"] = self.llamaparse_extract_charts
                    if self.llamaparse_target_pages is not None:
                        parser_kwargs["target_pages"] = self.llamaparse_target_pages
                    if self.llamaparse_bbox_top is not None and self.llamaparse_bbox_top > 0:
                        parser_kwargs["bbox_top"] = self.llamaparse_bbox_top
                    if self.llamaparse_bbox_bottom is not None and self.llamaparse_bbox_bottom > 0:
                        parser_kwargs["bbox_bottom"] = self.llamaparse_bbox_bottom
                    if self.llamaparse_user_prompt is not None:
                        parser_kwargs["user_prompt"] = self.llamaparse_user_prompt
                    if self.llamaparse_skip_diagonal_text:
                        parser_kwargs["skip_diagonal_text"] = True
                    if self.llamaparse_do_not_unroll_columns:
                        parser_kwargs["do_not_unroll_columns"] = True

                    try:
                        parser = LlamaParse(**parser_kwargs)
                        logger.info(f"LlamaParse initialized with {len(parser_kwargs)} configuration options")
                    except TypeError as e:
                        # Fallback for older LlamaParse versions
                        logger.warning(f"Some LlamaParse options not supported: {e}")
                        parser = LlamaParse(
                            api_key=self.llamaparse_api_key,
                            result_type=self.llamaparse_result_type,
                            verbose=True,
                            language=self.llamaparse_language,
                        )

                    self._readers_cache["llamaparse"] = parser
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

    def _load_excel_intelligently(self, file_path: Path, extra_info: Optional[dict] = None) -> List[LIDocument]:
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

    def _fallback_unstructured(self, file_path: Union[str, Path], extra_info: Optional[dict] = None) -> List[LIDocument]:
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
                logger.warning("No docs loaded with native readers, trying fallback")
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
                try:
                    return self._load_youtube_fallback(video_url, extra_info)
                except Exception as fallback_exc:
                    logger.error("YouTube fallback loader failed: %s", fallback_exc)
                    raise e from fallback_exc
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
