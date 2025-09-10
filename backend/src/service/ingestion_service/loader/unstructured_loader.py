"""
Enhanced Unstructured Loader - Clean, Unified Document Processing
Supports PDF, HTML, YouTube, XLSX/DOCX with intelligent spreadsheet handling.
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

import pandas as pd
from langchain_core.documents import Document
from unstructured.partition.auto import partition as u_partition

from src.service.ingestion_service.loader.semantic_double_pass_splitter import SemanticDoublePassMergingSplitterWithContext
from src.service.ingestion_service.progress_tracker import get_tracker
from src.service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT

logger = logging.getLogger(__name__)
TRANSCRIPT_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")

# -------------------- Helpers -------------------- #


def parse_timestamps(transcript_text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse YouTube transcript with timestamps."""
    segments, clean_text, offset_map = [], "", []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = TRANSCRIPT_PATTERN.match(line)
        if match:
            ts_str, text = match.groups()
            parts = ts_str.split(":")
            try:
                seconds = float(parts[0]) if len(parts) == 1 else int(parts[0]) * 60 + float(parts[1]) if len(parts) == 2 else int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                if text.strip():
                    segments.append({"start": seconds, "text": text.strip()})
            except ValueError:
                continue
        elif segments:
            segments[-1]["text"] += " " + line

    for i, seg in enumerate(segments):
        start_char = len(clean_text)
        clean_text += seg["text"] + " "
        end_char = len(clean_text) - 1
        end_time = segments[i + 1]["start"] if i + 1 < len(segments) else None
        offset_map.append({"start_char": start_char, "end_char": end_char, "start_time": seg["start"], "end_time": end_time})

    return clean_text.strip(), offset_map


def process_xlsx_intelligently(file_path: str, entry: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Enhanced XLSX processing that preserves tabular structure and creates logical chunks."""
    try:
        excel_file = pd.ExcelFile(file_path)
        chunks = []

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            if df.empty:
                continue

            # Clean the dataframe - remove completely empty rows/columns
            df = df.dropna(how="all").dropna(axis=1, how="all")

            if df.empty:
                continue

            headers = [str(col).strip() for col in df.columns]
            total_rows = len(df)

            # Create structured text representation of the entire sheet
            sheet_text = f"Sheet: {sheet_name}\nColumns: {', '.join(headers)}\n\n"

            # Convert all rows to structured text format
            for idx, row in df.iterrows():
                row_data = [f"{header}: {str(value).strip()}" for header, value in zip(headers, row) if pd.notna(value) and str(value).strip()]

                if row_data:
                    sheet_text += f"Row {idx + 1}: {' | '.join(row_data)}\n"

            # Create single chunk per sheet with rich metadata
            chunk_metadata = {"document_type": "spreadsheet", "spreadsheet_format": "xlsx", "sheet_name": sheet_name, "total_rows": total_rows, "headers": headers, "processing_method": "intelligent_sheet_conversion"}

            chunks.append((sheet_text.strip(), chunk_metadata))

        return chunks or [("Empty spreadsheet with no processable data.", {"document_type": "spreadsheet", "spreadsheet_format": "xlsx", "processing_method": "empty"})]

    except Exception as e:
        logger.warning(f"Intelligent XLSX processing failed: {e}, using fallback")
        try:
            elements = u_partition(file_path)
            text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
            return [(text, {"document_type": "spreadsheet", "spreadsheet_format": "xlsx", "processing_method": "unstructured_fallback"})]
        except Exception as fallback_error:
            logger.error(f"Both intelligent and fallback XLSX processing failed: {fallback_error}")
            return [("Failed to process spreadsheet content.", {"document_type": "spreadsheet", "spreadsheet_format": "xlsx", "processing_method": "failed", "error": str(fallback_error)})]


def get_chunk_times(chunk_text: str, full_text: str, offset_map: Optional[List[Dict[str, Any]]], curr_offset: int) -> Tuple[float, float, int]:
    """Map chunk to YouTube transcript timestamps."""
    start = max(full_text.find(chunk_text, curr_offset), curr_offset)
    end = start + len(chunk_text)
    start_time = end_time = 0.0

    if offset_map:
        # Find start time
        start_time = next((float(seg["start_time"]) for seg in offset_map if start >= seg["start_char"] <= seg["end_char"]), 0.0)
        # Find end time
        end_time = next((float(seg["end_time"] or start_time) for seg in reversed(offset_map) if end >= seg["start_char"] <= seg["end_char"]), start_time)

    return start_time, end_time, end


def _create_document(chunk_text: str, base_meta: Dict[str, Any], chunk_meta: Dict[str, Any], context: str) -> Document:
    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
    return Document(page_content=content, metadata={**base_meta, **chunk_meta})


def _get_base_metadata(path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    stat = os.stat(path)
    base_name = os.path.basename(path)
    title = entry.get("title") or os.path.splitext(base_name)[0]
    abs_path = os.path.abspath(path)

    def to_iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id": entry.get("id") or entry.get("graphql_id") or base_name,
        "title": title,
        "filename": base_name,
        "source_url": entry.get("source_url") or entry.get("link") or f"file://{abs_path}",
        "date": entry.get("date") or to_iso(getattr(stat, "st_ctime", stat.st_mtime)),
        "modified": entry.get("modified") or to_iso(stat.st_mtime),
        "mime_type": entry.get("mime_type") or mimetypes.guess_type(base_name)[0],
        "file_size": entry.get("file_size") or stat.st_size,
        "file_path": entry.get("file_path") or abs_path,
        "file_extension": os.path.splitext(path)[1].lower().lstrip("."),
        "source": entry.get("source") or title,
        "slug": entry.get("slug") or base_name.replace(" ", "-").lower(),
        "uri": entry.get("uri") or f"file://{abs_path}",
        "link": entry.get("link") or f"file://{abs_path}",
        "processing_timestamp": time.time(),
    }


# -------------------- Loader -------------------- #


def unstructured_loader(
    metadata_json_path: str,
    documents_dir: str,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Document]:
    start_time = time.time()
    tracker = get_tracker()

    # Load metadata systematically (support offset + limit)
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
        if offset:
            raw = raw[offset:]
        window = raw[:limit] if limit else raw
        entries = [e for e in window if e.get("filename")]

    logger.info(f"    ├── Loading {len(entries)} files from metadata")
    documents = []
    chunk_count = 0

    for i, entry in enumerate(entries, 1):
        filename = entry["filename"]
        tracker.log_file_start("document", filename, i, len(entries))

        path = Path(documents_dir) / filename if not os.path.isabs(filename) else Path(filename)
        if not path.exists():
            logger.warning(f"  │   └── ❌ File not found: {filename}")
            continue

        path_str = str(path)
        ext = os.path.splitext(path_str)[1].lower().lstrip(".")
        supported_exts = {"pdf", "html", "htm", "xlsx", "xls", "txt", "docx", "doc", "pptx", "ppt", "csv"}
        if ext not in supported_exts:
            continue

        base_meta = _get_base_metadata(path_str, entry)

        try:
            # Handle different file types with specific processing
            if ext in {"xlsx", "xls", "csv"}:
                tracker.log_file_phase("Parsing spreadsheet structure")
                xlsx_chunks = process_xlsx_intelligently(path, entry)

                # Process each spreadsheet sheet as a structured document
                splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100)
                total_file_chunks = 0

                for chunk_idx, (sheet_text, sheet_meta) in enumerate(xlsx_chunks):
                    chunk_base_meta = base_meta.copy()
                    chunk_base_meta.update(sheet_meta)

                    # Apply semantic chunking to the structured sheet text
                    # This allows proper chunking while preserving spreadsheet context
                    # Pass the whole sheet text as context for better contextualization
                    sheet_chunks = splitter.split_text(sheet_text, metadata={**chunk_base_meta, "__whole_document": sheet_text})

                    # Add each semantic chunk from this sheet
                    for semantic_chunk in sheet_chunks:
                        chunk_meta = dict(semantic_chunk.metadata)
                        chunk_meta.update({"sheet_index": chunk_idx, "total_sheets": len(xlsx_chunks), "chunk_size": len(semantic_chunk.page_content), "chunk_word_count": len(semantic_chunk.page_content.split())})

                        # Create enhanced context for spreadsheet chunk
                        context_parts = [f"Document: {base_meta['title']}"]
                        if sheet_meta.get("sheet_name"):
                            context_parts.append(f"Sheet: {sheet_meta['sheet_name']}")
                        if chunk_meta.get("context"):
                            context_parts.append(chunk_meta["context"])

                        context = " | ".join(context_parts)
                        documents.append(_create_document(semantic_chunk.page_content, chunk_base_meta, chunk_meta, context))

                    total_file_chunks += len(sheet_chunks)

                chunk_count += total_file_chunks
                file_tokens = sum(len(chunk_text.split()) for chunk_text, _ in xlsx_chunks)

            else:
                # Standard unstructured processing for other file types
                tracker.log_file_phase("Extracting content")
                elements = u_partition(path_str)
                whole_text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
                offset_map = is_transcript = None

                # Handle YouTube transcripts
                if ext == "txt" and entry.get("transcript_file") and TRANSCRIPT_PATTERN.search(whole_text):
                    tracker.log_file_phase("Parsing transcript timestamps")
                    clean_text, offset_map = parse_timestamps(whole_text)
                    is_transcript = True
                    base_meta.update({"transcript_type": "youtube", "has_timestamps": True})

                    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
                        tmp.write(clean_text)
                        tmp_path = tmp.name
                    try:
                        elements = u_partition(tmp_path)
                        whole_text = clean_text
                    finally:
                        os.unlink(tmp_path)

                # Chunking and contextualization
                splitter = SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100)
                chunks = splitter.split_text(whole_text, metadata=dict(entry))
                chunk_count += len(chunks)
                curr_offset = 0

                # Process chunks with enhanced metadata
                for idx, chunk_doc in enumerate(chunks):
                    chunk_text = chunk_doc.page_content
                    chunk_meta = dict(chunk_doc.metadata)
                    chunk_meta.pop("__whole_document", None)

                    # Add chunk-specific metadata
                    chunk_meta.update({"chunk_index": idx, "total_chunks": len(chunks), "chunk_size": len(chunk_text), "chunk_word_count": len(chunk_text.split())})

                    if is_transcript:
                        start_time_ts, end_time_ts, curr_offset = get_chunk_times(chunk_text, whole_text, offset_map, curr_offset)
                        duration = max(0, end_time_ts - start_time_ts)
                        chunk_meta.update({"start_time": start_time_ts, "end_time": end_time_ts, "duration": duration})

                    # Create enhanced context with file metadata
                    context_parts = [f"Document: {base_meta['title']}"]
                    if chunk_meta.get("context"):
                        context_parts.append(chunk_meta["context"])
                    if is_transcript:
                        context_parts.append(f"Transcript segment ({start_time_ts:.1f}s-{end_time_ts:.1f}s)")
                    context = " | ".join(context_parts)
                    documents.append(_create_document(chunk_text, base_meta, chunk_meta, context))

                # Log file completion
                file_tokens = sum(len(chunk.page_content.split()) for chunk in chunks)

            # Calculate chunks for this file
            file_chunks = total_file_chunks if ext in {"xlsx", "xls", "csv"} else len(chunks)
            tracker.log_file_complete(filename, file_chunks, file_tokens)

        except Exception as e:
            logger.warning(f"  │   └── ❌ Failed to process {filename}: {e}")
            if ext == "pdf":
                logger.error("  │       PDF processing failed - file may be corrupted, password-protected, or empty")
            continue

    # Enhanced summary logging
    total_tokens = sum(len(d.page_content.split()) for d in documents)
    duration = time.time() - start_time

    logger.info(f"  └── ✅ Processed {len(documents)} chunks, {total_tokens} tokens in {duration:.2f}s")

    # Update global tracker stats
    tracker.track_phase_stats("global", "chunks_created", chunk_count)
    tracker.track_phase_stats("global", "chunks_contextualized", len(documents))
    tracker.track_phase_stats("global", "total_tokens", total_tokens)

    return documents


__all__ = ["unstructured_loader"]
