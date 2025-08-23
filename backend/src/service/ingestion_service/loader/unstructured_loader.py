"""
Enhanced Unstructured Loader - Clean, Unified Document Processing
Supports PDF, HTML, YouTube, XLSX/DOCX, and generic text files with unified metadata.
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

from src.service.ingestion_service.loader.semantic_double_pass_splitter import SemanticDoublePassMergingSplitterWithContext
from src.service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT, YOUTUBE_TEXT_SPLIT_CHUNK_SIZE

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


def get_chunk_times(chunk_text: str, full_text: str, offset_map: Optional[List[Dict[str, Any]]], curr_offset: int) -> Tuple[float, float, int]:
    """Map chunk to YouTube transcript timestamps."""
    start = full_text.find(chunk_text, curr_offset)
    start = start if start != -1 else curr_offset
    end = start + len(chunk_text)
    curr_offset = end
    start_time, end_time = 0.0, 0.0
    if offset_map:
        for seg in offset_map:
            if start >= seg["start_char"] <= seg["end_char"]:
                start_time = float(seg["start_time"])
                break
        for seg in reversed(offset_map):
            if end >= seg["start_char"] <= seg["end_char"]:
                end_time = float(seg["end_time"] or start_time)
                break
    return start_time, end_time, curr_offset


def _create_document(chunk_text: str, base_meta: Dict[str, Any], chunk_meta: Dict[str, Any], context: str) -> Document:
    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
    return Document(page_content=content, metadata={**base_meta, **chunk_meta})


def _get_base_metadata(path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    stat, base_name = os.stat(path), os.path.basename(path)
    title = entry.get("title") or os.path.splitext(base_name)[0]
    mime_type = mimetypes.guess_type(base_name)[0]
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
        "mime_type": entry.get("mime_type") or mime_type,
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


def unstructured_loader(metadata_json_path: str, documents_dir: str, limit: Optional[int] = None) -> List[Document]:
    start_time = time.time()

    with tqdm(total=1, desc="Loading metadata", leave=False) as pbar:
        with open(metadata_json_path, "r", encoding="utf-8") as f:
            entries = [e for e in (json.load(f)[:limit] if limit else json.load(f)) if e.get("filename")]
        pbar.update(1)

    logger.info(f"[Unstructured] Processing {len(entries)} files")

    # Splitters
    splitters = {
        "pdf": SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100),
        "html": SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100),
        "youtube": SemanticDoublePassMergingSplitterWithContext(max_chunk_size=YOUTUBE_TEXT_SPLIT_CHUNK_SIZE, min_chunk_size=100),
        "generic": SemanticDoublePassMergingSplitterWithContext(max_chunk_size=CHUNK_SIZE, min_chunk_size=100),
    }

    documents = []

    for entry in tqdm(entries, desc="Processing files", colour="yellow"):
        filename = entry["filename"]
        path = Path(documents_dir) / filename if not os.path.isabs(filename) else Path(filename)
        if not path.exists():
            logger.warning(f"File not found: {filename}")
            continue
        path = str(path)
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext not in {"pdf", "html", "htm", "xlsx", "xls", "txt", "docx", "doc", "pptx", "ppt", "csv"}:
            continue

        base_meta = _get_base_metadata(path, entry)

        try:
            # Partitioning
            with tqdm(total=1, desc=f"Partitioning {filename}", leave=False) as pbar:
                if ext == "pdf":
                    try:
                        # Try with standard options first
                        elements = partition_pdf(path, include_page_breaks=True, infer_table_structure=True)
                    except Exception as pdf_error:
                        logger.warning(f"Standard PDF partitioning failed for {filename}: {pdf_error}")

                        # Try fallback options for corrupted PDFs
                        try:
                            logger.info(f"Attempting fallback PDF processing for {filename}")
                            # Try without table structure inference
                            elements = partition_pdf(path, include_page_breaks=True, infer_table_structure=False)
                        except Exception as fallback_error:
                            logger.warning(f"Fallback PDF partitioning also failed for {filename}: {fallback_error}")

                            # Try with minimal options
                            try:
                                logger.info(f"Attempting minimal PDF processing for {filename}")
                                elements = partition_pdf(path, include_page_breaks=False, infer_table_structure=False)
                            except Exception as minimal_error:
                                logger.warning(f"Minimal PDF processing also failed for {filename}: {minimal_error}")

                                # Try with different strategy options
                                try:
                                    logger.info(f"Attempting alternative PDF strategy for {filename}")
                                    elements = partition_pdf(path, include_page_breaks=False, infer_table_structure=False, strategy="fast")
                                except Exception as strategy_error:
                                    logger.warning(f"Alternative strategy also failed for {filename}: {strategy_error}")

                                    # Final attempt with auto partitioning
                                    try:
                                        logger.info(f"Attempting auto partitioning for {filename}")
                                        elements = u_partition(path)
                                    except Exception as auto_error:
                                        logger.error(f"All unstructured PDF processing attempts failed for {filename}: {auto_error}")
                                        raise auto_error
                elif ext in {"html", "htm"}:
                    elements = partition_html(path)
                else:
                    elements = u_partition(path)
                pbar.update(1)

            whole_text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())
            offset_map, is_transcript = None, False

            if ext == "txt" and entry.get("transcript_file") and TRANSCRIPT_PATTERN.search(whole_text):
                with tqdm(total=1, desc=f"Parsing transcript {filename}", leave=False) as pbar:
                    clean_text, offset_map = parse_timestamps(whole_text)
                    is_transcript = True
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
                        tmp.write(clean_text)
                        tmp_path = tmp.name
                    try:
                        elements = u_partition(tmp_path)
                    finally:
                        os.unlink(tmp_path)
                    whole_text = clean_text
                    pbar.update(1)

            with tqdm(total=1, desc=f"Splitting {filename}", leave=False) as pbar:
                splitter = splitters["youtube"] if is_transcript else splitters.get(ext, splitters["generic"])
                chunks = splitter.split_text(whole_text, metadata=dict(entry))
                pbar.update(1)

            curr_offset = 0

            # Process chunks
            for idx, chunk_doc in enumerate(chunks):
                chunk_text = chunk_doc.page_content
                chunk_meta = dict(chunk_doc.metadata)
                chunk_meta.pop("__whole_document", None)

                if is_transcript:
                    start_time, end_time, curr_offset = get_chunk_times(chunk_text, whole_text, offset_map, curr_offset)
                    chunk_meta.update({"start_time": start_time, "end_time": end_time})

                context = f"Document: {base_meta['title']}"
                if chunk_meta.get("context"):
                    context += f" | {chunk_meta['context']}"

                documents.append(_create_document(chunk_text, base_meta, chunk_meta, context))

        except Exception as e:
            logger.warning(f"Failed to process {filename}: {e}")

            # Provide more specific error information for PDF issues
            if ext == "pdf":
                logger.error(f"PDF processing completely failed for {filename}. This file may be:")
                logger.error("  1. Corrupted or damaged")
                logger.error("  2. Password-protected")
                logger.error("  3. In an unsupported format")
                logger.error("  4. Empty or contains no text")
                logger.error(f"  5. Error details: {str(e)}")

            continue

    # Count PDF files processed
    pdf_files_processed = sum(1 for entry in entries if entry.get("filename", "").lower().endswith(".pdf"))
    if pdf_files_processed > 0:
        logger.info(f"[Unstructured] PDF processing summary: {pdf_files_processed} PDF files attempted")

    logger.info(f"[Unstructured] Processed {len(documents)} chunks, {sum(len(d.page_content.split()) for d in documents)} tokens in {time.time()-start_time:.2f}s")
    return documents


__all__ = ["unstructured_loader"]
