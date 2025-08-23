"""
Enhanced Unstructured Loader - Clean, Unified Document Processing

This module provides a clean, unified loader that replaces the separate HTML, PDF, and YouTube loaders
while preserving all their specialized features. It uses the Unstructured library for robust document
processing with enhanced capabilities.

Features:
- PDF: Page mapping, coordinate tracking, position percentages
- HTML: Section hierarchy extraction, anchor tracking
- YouTube: Timestamp parsing, video metadata
- XLSX/DOCX: Additional format support
- Unified metadata schema across all document types
"""

import json
import logging
import mimetypes
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from tqdm import tqdm
from unstructured.partition.auto import partition as u_partition
from unstructured.partition.html import partition_html
from unstructured.partition.pdf import partition_pdf

from src.schemas.metadata import (
    HTMLChunkMetadata,
    PDFChunkMetadata,
    XLSXChunkMetadata,
    YouTubeChunkMetadata,
)
from src.service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
from src.service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT, YOUTUBE_TEXT_SPLIT_CHUNK_SIZE

logger = logging.getLogger(__name__)
TRANSCRIPT_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")


def parse_timestamps(transcript_text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse timestamped transcript, return clean text and offset map."""
    segments = []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = TRANSCRIPT_PATTERN.match(line)
        if match:
            ts_str, text = match.groups()
            parts = ts_str.split(":")
            try:
                if len(parts) == 3:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    seconds = int(parts[0]) * 60 + float(parts[1])
                else:
                    seconds = float(parts[0])
                if text.strip():
                    segments.append({"start": seconds, "text": text.strip()})
            except ValueError:
                continue
        else:
            if segments:
                segments[-1]["text"] = str(segments[-1]["text"]) + " " + line

    clean_text = ""
    offset_map = []
    for i, seg in enumerate(segments):
        start_char = len(clean_text)
        clean_text += str(seg["text"]) + " "
        end_char = len(clean_text) - 1
        end_time = segments[i + 1]["start"] if i + 1 < len(segments) else None
        offset_map.append({"start_char": start_char, "end_char": end_char, "start_time": seg["start"], "end_time": end_time})
    return clean_text.strip(), offset_map


def get_chunk_times(chunk_text: str, full_text: str, offset_map: Optional[List[Dict[str, Any]]], curr_offset: int) -> Tuple[float, float, int]:
    """Get start/end times for chunk."""
    chunk_start = full_text.find(chunk_text, curr_offset)
    if chunk_start == -1:
        chunk_start = curr_offset
    chunk_end = chunk_start + len(chunk_text)

    start_time = 0.0
    end_time = 0.0

    if offset_map:
        for segment in offset_map:
            if chunk_start >= segment["start_char"] and chunk_start <= segment["end_char"]:
                start_time = float(segment["start_time"])
                break

        for segment in reversed(offset_map):
            if chunk_end >= segment["start_char"] and chunk_end <= segment["end_char"]:
                end_time = float(segment["end_time"]) if segment["end_time"] is not None else start_time
                break

    return start_time, end_time, chunk_end


def unstructured_loader(metadata_json_path: str, documents_dir: str, limit: Optional[int] = None) -> List[Document]:
    """
    Enhanced unified document loader function.

    This function provides the same interface as the original unstructured_loader
    while offering enhanced capabilities for PDF, HTML, and YouTube processing.

    Args:
        metadata_json_path: Path to metadata JSON file
        documents_dir: Directory containing document files
        limit: Optional limit on number of documents to process

    Returns:
        List of processed Document objects with enhanced metadata
    """
    start_time = time.time()

    with open(metadata_json_path, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    # Filter valid entries
    entries = []
    to_process = raw_entries[:limit] if limit and limit > 0 else raw_entries
    for entry in to_process:
        filename = entry.get("filename")
        if isinstance(filename, str) and filename.strip():
            entry["filename"] = filename.strip()
            entries.append(entry)

    logger.info(f"[Unstructured] Processing {len(entries)} files")
    # Use different splitters based on file type - will be set per file type
    html_splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100)
    pdf_splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100)
    youtube_splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=YOUTUBE_TEXT_SPLIT_CHUNK_SIZE, min_chunk_size=100)
    generic_splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100)
    documents = []

    for entry in tqdm(entries, desc="Processing files"):
        filename = entry["filename"]

        # Resolve file path
        if os.path.isabs(filename) and os.path.exists(filename):
            path = filename
        else:
            path = Path(documents_dir) / filename
            if not path.exists():
                for found in Path(documents_dir).rglob(Path(filename).name):
                    if found.is_file():
                        path = found
                        break

        if not path or not Path(path).exists():
            logger.warning(f"File not found: {filename}")
            continue

        path = str(path)
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext not in {"pdf", "html", "htm", "xlsx", "xls", "txt", "docx", "doc", "pptx", "ppt", "csv"}:
            continue

        try:
            # Base metadata
            stat = os.stat(path)
            base_name = os.path.basename(path)
            title = entry.get("title") or os.path.splitext(base_name)[0]
            mime_type, _ = mimetypes.guess_type(base_name)
            abs_path = os.path.abspath(path)

            def to_iso(ts):
                return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            base_meta = {
                "id": entry.get("id") or entry.get("graphql_id") or base_name,
                "title": title,
                "filename": base_name,
                "source_url": entry.get("source_url") or entry.get("link") or f"file://{abs_path}",
                "date": entry.get("date") or to_iso(getattr(stat, "st_ctime", stat.st_mtime)),
                "modified": entry.get("modified") or to_iso(stat.st_mtime),
                "mime_type": entry.get("mime_type") or mime_type,
                "file_size": entry.get("file_size") or stat.st_size,
                "file_path": entry.get("file_path") or abs_path,
                "file_extension": ext,
                "source": entry.get("source") or title,
                "slug": entry.get("slug") or base_name.replace(" ", "-").lower(),
                "uri": entry.get("uri") or f"file://{abs_path}",
                "link": entry.get("link") or f"file://{abs_path}",
                "processing_timestamp": time.time(),
            }

            # File processing - Check for YouTube transcript specifically
            if ext == "txt" and entry.get("transcript_file"):
                # YouTube transcript processing
                with open(path, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                if TRANSCRIPT_PATTERN.search(raw_content):
                    clean_text, offset_map = parse_timestamps(raw_content)
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
                        tmp.write(clean_text)
                        tmp_path = tmp.name
                    try:
                        elements = u_partition(filename=tmp_path)
                    finally:
                        os.unlink(tmp_path)
                    whole_text = clean_text
                    is_transcript = True
                else:
                    # Fallback for YouTube files without proper timestamps
                    elements = u_partition(filename=path)
                    whole_text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
                    offset_map = None
                    is_transcript = False
            else:
                if ext == "pdf":
                    elements = partition_pdf(filename=path, include_page_breaks=True, infer_table_structure=True)
                elif ext in ["html", "htm"]:
                    elements = partition_html(filename=path)
                else:
                    elements = u_partition(filename=path)

                whole_text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
                offset_map = None
                is_transcript = False

            # Chunking
            if is_transcript:
                # YouTube transcript chunking with timestamps
                metadata_for_splitting = dict(entry)
                metadata_for_splitting["metadata"] = dict(entry.get("metadata") or {})
                metadata_for_splitting["__whole_document"] = whole_text

                chunks = youtube_splitter.split_text(whole_text, metadata=metadata_for_splitting)
                curr_offset = 0

                for chunk_index, chunk_doc in enumerate(chunks):
                    chunk_text = chunk_doc.page_content
                    chunk_meta = dict(chunk_doc.metadata)
                    chunk_meta.pop("__whole_document", None)

                    start_time, end_time, curr_offset = get_chunk_times(chunk_text, whole_text, offset_map, curr_offset)

                    complete_meta = {
                        **base_meta,
                        **chunk_meta,
                        "chunk_index": chunk_index,
                        "total_chunks_in_document": len(chunks),
                        "chunking_strategy": youtube_splitter.__class__.__name__,
                        "word_count": len(chunk_text.split()),
                        "content_length": len(chunk_text),
                        "validation_status": "ok",
                        "metadata": chunk_meta.get("metadata", {}),
                        "video_id": entry.get("video_id", "unknown"),
                        "total_chunks_in_video": len(chunks),
                        "start_time": start_time,
                        "end_time": end_time,
                        "transcript_available": True,
                        "transcript_file": abs_path,
                    }

                    # Add YouTube fields
                    for field in ["duration", "view_count", "like_count", "comment_count", "uploader", "channel", "channel_id", "tags", "categories", "thumbnail", "uploader_url", "availability", "live_status", "release_timestamp", "chapters", "heatmap", "transcript_length", "transcript_word_count"]:
                        if field in entry:
                            complete_meta[field] = entry[field]

                    try:
                        YouTubeChunkMetadata(**complete_meta)
                    except Exception as e:
                        logger.warning(f"YouTube metadata validation failed: {e}")
                        continue

                    context = f"Document: {title} | Transcript: {start_time:.1f}s-{end_time:.1f}s"
                    if chunk_meta.get("context"):
                        context += f" | {chunk_meta['context']}"

                    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
                    documents.append(Document(page_content=content, metadata=complete_meta))

            elif ext == "pdf":
                # PDF processing with page mapping
                page_mapping: Dict[int, Dict[str, Any]] = {}
                char_offset = 0

                for element in elements:
                    element_text = str(element).strip()
                    if not element_text:
                        continue

                    element_metadata = getattr(element, "metadata", None)
                    if element_metadata:
                        metadata_dict = element_metadata.to_dict() if hasattr(element_metadata, "to_dict") else {}
                        page_num = int(metadata_dict.get("page_number", 1))
                    else:
                        page_num = 1

                    if page_num not in page_mapping:
                        page_mapping[page_num] = {"start_char": char_offset, "end_char": char_offset, "elements": []}

                    page_mapping[page_num]["elements"].append({"text": element_text, "start_char": char_offset, "end_char": char_offset + len(element_text), "category": getattr(element, "category", "Unknown")})

                    page_mapping[page_num]["end_char"] = char_offset + len(element_text) + 2
                    char_offset += len(element_text) + 2

                chunks = pdf_splitter.split_text(whole_text, metadata=entry)
                curr_offset = 0

                for chunk_index, chunk_doc in enumerate(chunks):
                    chunk_text = chunk_doc.page_content
                    chunk_start = whole_text.find(chunk_text, curr_offset)
                    if chunk_start == -1:
                        chunk_start = curr_offset
                    chunk_end = chunk_start + len(chunk_text)
                    curr_offset = chunk_end

                    # Find pages for chunk
                    pages_covered = []
                    pages_info = []

                    for page_num, page_data in page_mapping.items():
                        page_start = int(page_data["start_char"])
                        page_end = int(page_data["end_char"])

                        if chunk_start < page_end and chunk_end > page_start:
                            pages_covered.append(page_num)

                            overlap_start = max(chunk_start, page_start)
                            overlap_end = min(chunk_end, page_end)
                            page_length = page_end - page_start

                            if page_length > 0:
                                start_pct = (overlap_start - page_start) / page_length
                                end_pct = (overlap_end - page_start) / page_length

                                span = end_pct - start_pct
                                if span >= 0.95:
                                    position = "full"
                                elif start_pct <= 0.15 and end_pct <= 0.5:
                                    position = "top"
                                elif start_pct >= 0.5 and end_pct >= 0.85:
                                    position = "bottom"
                                elif start_pct > 0.15 and end_pct < 0.85:
                                    position = "middle"
                                else:
                                    position = "partial"

                                pages_info.append({"page": page_num, "start_pct": round(start_pct, 3), "end_pct": round(end_pct, 3), "position": position})

                    chunk_meta = dict(chunk_doc.metadata)
                    complete_meta = {
                        **base_meta,
                        **chunk_meta,
                        "chunk_index": chunk_index,
                        "total_chunks_in_document": len(chunks),
                        "chunking_strategy": pdf_splitter.__class__.__name__,
                        "word_count": len(chunk_text.split()),
                        "content_length": len(chunk_text),
                        "validation_status": "ok",
                        "metadata": chunk_meta.get("metadata", {}),
                        "pages": pages_covered,
                        "pages_info": pages_info,
                        "total_pages": len(page_mapping),
                        "page_number": pages_covered[0] if pages_covered else 1,
                        "total_chunks_in_page": 0,
                    }

                    try:
                        PDFChunkMetadata(**complete_meta)
                    except Exception as e:
                        logger.warning(f"PDF metadata validation failed: {e}")
                        continue

                    context = f"Document: {title} | Pages: {pages_covered}"
                    if chunk_meta.get("context"):
                        context += f" | {chunk_meta['context']}"

                    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
                    documents.append(Document(page_content=content, metadata=complete_meta))

            elif ext in ["html", "htm"]:
                # HTML processing with section hierarchy
                sections = []
                current_section: Dict[str, Any] = {"path": [], "texts": [], "anchors": []}

                for element in elements:
                    element_text = str(element).strip()
                    if not element_text:
                        continue

                    if getattr(element, "category", "") == "Title":
                        if current_section["texts"]:
                            sections.append(current_section.copy())

                        # Determine heading level
                        element_metadata = getattr(element, "metadata", None)
                        level = 3  # default

                        if element_metadata:
                            metadata_dict = element_metadata.to_dict() if hasattr(element_metadata, "to_dict") else {}
                            for key, value in metadata_dict.items():
                                key_val_str = f"{key}{value}".lower()
                                for h_level in range(1, 7):
                                    if f"h{h_level}" in key_val_str:
                                        level = h_level
                                        break

                        # Fallback: text-based analysis
                        if len(element_text) < 50 and element_text.isupper():
                            level = 1
                        elif len(element_text) < 80:
                            level = 2

                        current_section["path"] = current_section["path"][: level - 1] + [element_text]
                        current_section["texts"] = []
                        current_section["anchors"] = []
                    else:
                        current_section["texts"].append(element_text)

                        element_metadata = getattr(element, "metadata", None)
                        anchor = None
                        if element_metadata:
                            metadata_dict = element_metadata.to_dict() if hasattr(element_metadata, "to_dict") else {}
                            anchor = metadata_dict.get("link_urls", [None])[0] if metadata_dict.get("link_urls") else None

                        current_section["anchors"].append(anchor)

                if current_section["texts"]:
                    sections.append(current_section)

                # Create chunks from sections
                for sec_idx, section in enumerate(sections):
                    section_text = "\n\n".join(section["texts"])
                    if not section_text.strip():
                        continue

                    chunks = html_splitter.split_text(section_text, metadata=entry)
                    curr_offset = 0

                    for chunk_idx, chunk_doc in enumerate(chunks):
                        chunk_text = chunk_doc.page_content
                        chunk_start = section_text.find(chunk_text, curr_offset)
                        if chunk_start == -1:
                            chunk_start = curr_offset
                        chunk_end = chunk_start + len(chunk_text)
                        curr_offset = chunk_end

                        anchor = section["anchors"][0] if section["anchors"] else None

                        chunk_meta = dict(chunk_doc.metadata)
                        complete_meta = {
                            **base_meta,
                            **chunk_meta,
                            "chunk_index": chunk_idx,
                            "total_chunks_in_document": len(chunks),
                            "chunking_strategy": html_splitter.__class__.__name__,
                            "word_count": len(chunk_text.split()),
                            "content_length": len(chunk_text),
                            "validation_status": "ok",
                            "metadata": chunk_meta.get("metadata", {}),
                            "section_path": section["path"],
                            "section_index": sec_idx,
                            "total_chunks_in_section": len(chunks),
                            "anchor": anchor,
                            "html_url": f"{entry.get('link', '')}#{anchor}" if anchor else entry.get("link", ""),
                            "chunk_start": chunk_start,
                            "chunk_end": chunk_end,
                        }

                        try:
                            HTMLChunkMetadata(**complete_meta)
                        except Exception as e:
                            logger.warning(f"HTML metadata validation failed: {e}")
                            continue

                        section_context = " > ".join(section["path"]) if section["path"] else "Document"
                        context = f"Document: {title} | Section: {section_context}"
                        if chunk_meta.get("context"):
                            context += f" | {chunk_meta['context']}"

                        content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
                        documents.append(Document(page_content=content, metadata=complete_meta))

            else:
                # Generic file processing for XLSX, DOCX, etc.
                all_chunks = []

                for element_index, element in enumerate(elements):
                    element_text = str(element).strip()
                    if not element_text:
                        continue

                    metadata_for_splitting = dict(entry)
                    metadata_bag = dict(entry.get("metadata") or {})
                    if hasattr(element, "metadata"):
                        metadata_bag.update(element.metadata.to_dict())
                    metadata_for_splitting["metadata"] = metadata_bag
                    metadata_for_splitting["__whole_document"] = whole_text

                    element_chunks = generic_splitter.split_text(element_text, metadata=metadata_for_splitting)

                    for chunk_doc in element_chunks:
                        chunk_text = chunk_doc.page_content
                        chunk_meta = dict(chunk_doc.metadata)
                        chunk_meta.pop("__whole_document", None)

                        all_chunks.append({"text": chunk_text, "metadata": chunk_meta, "element_index": element_index, "element_category": getattr(element, "category", None), "element_type": element.__class__.__name__})

                # Finalize chunks
                total_chunks = len(all_chunks)

                for chunk_index, chunk_data in enumerate(all_chunks):
                    chunk_text = str(chunk_data["text"])
                    chunk_meta = dict(chunk_data["metadata"])

                    complete_meta = {
                        **base_meta,
                        **chunk_meta,
                        "chunk_index": chunk_index,
                        "total_chunks_in_document": total_chunks,
                        "chunking_strategy": generic_splitter.__class__.__name__,
                        "word_count": len(chunk_text.split()),
                        "content_length": len(chunk_text),
                        "validation_status": "ok",
                        "metadata": chunk_meta.get("metadata", {}),
                        "element_index": chunk_data["element_index"],
                        "element_category": chunk_data["element_category"],
                        "element_type": chunk_data["element_type"],
                    }

                    # Type-specific validation
                    if ext in ["xlsx", "xls"]:
                        complete_meta.update({"sheet_name": None, "total_sheets": 1, "total_chunks_in_sheet": total_chunks, "row_start": None, "row_end": None, "column_start": None, "column_end": None})
                        try:
                            XLSXChunkMetadata(**complete_meta)
                        except Exception as e:
                            logger.warning(f"XLSX metadata validation failed: {e}")
                            continue

                    element_context = chunk_data["element_category"] or ""
                    context = f"Document: {title}"
                    if element_context:
                        context += f" | Element: {element_context}"
                    if chunk_meta.get("context"):
                        context += f" | {chunk_meta['context']}"

                    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
                    documents.append(Document(page_content=content, metadata=complete_meta))

        except Exception as e:
            logger.warning(f"Failed to process {filename}: {e}")
            continue

    elapsed = time.time() - start_time
    total_tokens = sum(len(doc.page_content.split()) for doc in documents)
    logger.info(f"[Unstructured] Processed {len(documents)} chunks, {total_tokens} tokens in {elapsed:.2f}s")

    return documents


__all__ = ["unstructured_loader"]
