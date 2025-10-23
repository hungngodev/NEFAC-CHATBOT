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
from typing import Any, Dict, List, Optional, Set, Tuple

from llama_index.core.schema import BaseNode, TextNode
from unstructured.partition.auto import partition as u_partition

from src.service.ingestion_service.llamaindex.document_loader import (
    UnifiedDocumentLoader,
)
from src.service.ingestion_service.llamaindex.node_parser import (
    build_nodes_from_text,
)
from src.service.ingestion_service.progress_tracker import get_tracker
from src.service.ingestion_service.settings import (
    CONTEXT_FORMAT,
    LLAMAPARSE_API_KEY,
    LLAMAPARSE_AUTO_MODE,
    LLAMAPARSE_ENABLE,
    LLAMAPARSE_EXTRACT_CHARTS,
    LLAMAPARSE_RESULT_TYPE,
)

from .spreadsheet_utils import process_xlsx_intelligently

logger = logging.getLogger(__name__)
TRANSCRIPT_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")
_TRUTHY = {"1", "true", "yes", "on"}

USE_LLAMAINDEX_READERS = os.getenv("USE_LLAMAINDEX_READERS", "true").lower() in _TRUTHY
LLAMAPARSE_ENABLED = LLAMAPARSE_ENABLE
SUPPORTED_LI_EXTS = {"pdf", "html", "htm", "docx", "doc", "ppt", "pptx", "txt"}

LLAMA_LOADER: Optional[UnifiedDocumentLoader]
if USE_LLAMAINDEX_READERS:
    LLAMA_LOADER = UnifiedDocumentLoader(
        use_llamaparse=LLAMAPARSE_ENABLED,
        llamaparse_api_key=LLAMAPARSE_API_KEY,
        llamaparse_auto_mode=LLAMAPARSE_AUTO_MODE,
        llamaparse_extract_charts=LLAMAPARSE_EXTRACT_CHARTS,
        llamaparse_result_type=LLAMAPARSE_RESULT_TYPE,
        fallback_to_unstructured=True,
    )
else:
    LLAMA_LOADER = None

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
    start = max(full_text.find(chunk_text, curr_offset), curr_offset)
    end = start + len(chunk_text)
    start_time = end_time = 0.0

    if offset_map:
        # Find start time: segment whose char span covers 'start'
        start_time = next(
            (float(seg["start_time"]) for seg in offset_map if seg["start_char"] <= start <= seg["end_char"]),
            0.0,
        )
        # Find end time: segment whose char span covers 'end'
        end_time = next(
            (float(seg["end_time"] or start_time) for seg in reversed(offset_map) if seg["start_char"] <= end <= seg["end_char"]),
            start_time,
        )

    return start_time, end_time, end


def _parse_pdf_with_llamaparse(file_path: str) -> Optional[str]:
    """Parse PDF into text using LlamaParse if available and configured."""

    try:
        from llama_parse import LlamaParse  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("LlamaParse unavailable: %s", exc)
        return None
    api_key = LLAMAPARSE_API_KEY
    if not api_key:
        logger.warning("LLAMAPARSE_API_KEY not set; skipping LlamaParse")
        return None

    try:
        parser_kwargs = {
            "api_key": api_key,
            "result_type": LLAMAPARSE_RESULT_TYPE or "text",
        }
        parser = LlamaParse(**parser_kwargs)

        optional_flags = {
            "auto_mode": LLAMAPARSE_AUTO_MODE,
            "extract_charts": LLAMAPARSE_EXTRACT_CHARTS,
        }
        parsing_config = getattr(parser, "parsing_config", None)
        if isinstance(parsing_config, dict):  # pragma: no branch - recent versions expose dict
            parsing_config.update({k: v for k, v in optional_flags.items() if v is not None})
        else:  # pragma: no cover - depends on llama-parse version
            for key, value in optional_flags.items():
                if value is None:
                    continue
                try:
                    setattr(parser, key, value)
                except AttributeError:
                    logger.debug("LlamaParse option '%s' not supported on this version", key)

        results = parser.load_data(file_path)
        texts: List[str] = []
        for result in results:
            text = getattr(result, "text", None)
            if callable(text):  # Some versions expose text as callable property
                text = text()
            if not text:
                maybe_get_content = getattr(result, "get_content", None)
                if callable(maybe_get_content):
                    text = maybe_get_content()
            if text:
                stripped = str(text).strip()
                if stripped:
                    texts.append(stripped)

        joined = "\n\n".join(texts)
        return joined or None
    except Exception as exc:  # pragma: no cover - network/service failures
        logger.error("LlamaParse failed for %s: %s", file_path, exc)
        return None


def _create_node(
    chunk_text: str,
    base_meta: Dict[str, Any],
    chunk_meta: Dict[str, Any],
    context: str,
    raw_node: Optional[BaseNode] = None,
) -> TextNode:
    metadata = {**base_meta, **chunk_meta}
    content = CONTEXT_FORMAT.format(context=context, chunk=chunk_text)
    node = TextNode(
        text=content,
        metadata=metadata,
        id_=getattr(raw_node, "node_id", None) if raw_node is not None else None,
        relationships=getattr(raw_node, "relationships", None) if raw_node is not None else None,
    )

    if raw_node is not None:
        embedding = getattr(raw_node, "embedding", None)
        if embedding is not None:
            node.embedding = embedding
        for attr in ("excluded_embed_metadata_keys", "excluded_llm_metadata_keys"):
            value = getattr(raw_node, attr, None)
            if value:
                setattr(node, attr, value)

    return node


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
    file_type: Optional[str] = None,
    include_only: Optional[Set[str]] = None,
    processed_filenames: Optional[Set[str]] = None,
) -> List[TextNode]:
    start_time = time.time()
    tracker = get_tracker()

    # Load metadata systematically (support offset + limit)
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
        if offset:
            raw = raw[offset:]
        window = raw[:limit] if limit else raw
        entries = [e for e in window if e.get("filename")]

    if include_only:
        normalized_targets = {str(name) for name in include_only}
        entries = [entry for entry in entries if entry["filename"] in normalized_targets]
        if not entries:
            logger.info("    ├── No matching documents found in include_only filter")

    logger.info(f"    ├── Loading {len(entries)} files from metadata")
    nodes: List[TextNode] = []
    chunk_count = 0
    for i, entry in enumerate(entries, 1):
        filename = entry["filename"]
        tracker.log_file_start(file_type or "document", filename, i, len(entries))

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
        document_base_meta = base_meta.copy()
        document_base_meta.update({k: v for k, v in (entry or {}).items() if v is not None})

        try:
            if ext in {"xlsx", "xls", "csv"}:
                tracker.log_file_phase("Parsing spreadsheet structure")
                xlsx_chunks = process_xlsx_intelligently(path, entry)

                # Process each spreadsheet sheet as a structured document
                total_file_chunks = 0
                file_tokens = 0

                for chunk_idx, (sheet_text, sheet_meta) in enumerate(xlsx_chunks):
                    chunk_base_meta = document_base_meta.copy()
                    chunk_base_meta.update(sheet_meta)

                    sheet_nodes = build_nodes_from_text(sheet_text, chunk_base_meta)
                    total_file_chunks += len(sheet_nodes)
                    file_tokens += sum(len(raw_node.get_content().split()) for raw_node in sheet_nodes)

                    for idx, raw_node in enumerate(sheet_nodes):
                        chunk_text = raw_node.get_content()
                        node_meta = dict(raw_node.metadata or {})
                        chunk_meta = {
                            **node_meta,
                            "sheet_index": chunk_idx,
                            "total_sheets": len(xlsx_chunks),
                            "chunk_index": idx,
                            "total_chunks": len(sheet_nodes),
                            "chunk_size": len(chunk_text),
                            "chunk_word_count": len(chunk_text.split()),
                        }

                        context_parts = [f"Document: {base_meta['title']}"]
                        if sheet_meta.get("sheet_name"):
                            context_parts.append(f"Sheet: {sheet_meta['sheet_name']}")
                        summary = node_meta.get("section_summary") or node_meta.get("window")
                        if summary:
                            context_parts.append(str(summary))

                        context = " | ".join(context_parts)
                        nodes.append(_create_node(chunk_text, chunk_base_meta, chunk_meta, context, raw_node=raw_node))

            elif ext == "txt" and entry.get("transcript_file"):
                tracker.log_file_phase("Parsing transcript timestamps")
                with open(path_str, "r", encoding="utf-8") as transcript_file:
                    raw_transcript = transcript_file.read()

                clean_text, offset_map = parse_timestamps(raw_transcript)
                base_meta.update({"transcript_type": "youtube", "has_timestamps": True})

                raw_nodes = build_nodes_from_text(clean_text, document_base_meta)
                total_file_chunks = len(raw_nodes)
                file_tokens = sum(len(raw_node.get_content().split()) for raw_node in raw_nodes)
                curr_offset = 0

                for idx, raw_node in enumerate(raw_nodes):
                    chunk_text = raw_node.get_content()
                    node_meta = dict(raw_node.metadata or {})
                    chunk_meta = {
                        **node_meta,
                        "chunk_index": idx,
                        "total_chunks": total_file_chunks,
                        "chunk_size": len(chunk_text),
                        "chunk_word_count": len(chunk_text.split()),
                    }

                    start_time_ts, end_time_ts, curr_offset = get_chunk_times(
                        chunk_text,
                        clean_text,
                        offset_map,
                        curr_offset,
                    )
                    chunk_meta.update(
                        {
                            "start_time": start_time_ts,
                            "end_time": end_time_ts,
                            "duration": max(0, end_time_ts - start_time_ts),
                        }
                    )

                    context_parts = [f"Document: {base_meta['title']}"]
                    summary = node_meta.get("section_summary") or node_meta.get("window")
                    if summary:
                        context_parts.append(str(summary))
                    context_parts.append(f"Transcript segment ({start_time_ts:.1f}s-{end_time_ts:.1f}s)")
                    context = " | ".join(context_parts)
                    nodes.append(
                        _create_node(
                            chunk_text,
                            document_base_meta,
                            chunk_meta,
                            context,
                            raw_node=raw_node,
                        )
                    )

            elif LLAMA_LOADER and ext in SUPPORTED_LI_EXTS:
                tracker.log_file_phase("LlamaIndex reader ingestion")
                li_docs = LLAMA_LOADER.load_file(path_str, extra_info=document_base_meta)

                raw_nodes: List[BaseNode] = []
                for doc in li_docs:
                    doc_nodes = build_nodes_from_text(
                        doc.get_content(),
                        doc.metadata or document_base_meta,
                    )
                    raw_nodes.extend(doc_nodes)

                total_file_chunks = len(raw_nodes)
                file_tokens = sum(len(raw_node.get_content().split()) for raw_node in raw_nodes)

                for idx, raw_node in enumerate(raw_nodes):
                    chunk_text = raw_node.get_content()
                    node_meta = dict(raw_node.metadata or {})
                    chunk_meta = {
                        **node_meta,
                        "chunk_index": idx,
                        "total_chunks": total_file_chunks,
                        "chunk_size": len(chunk_text),
                        "chunk_word_count": len(chunk_text.split()),
                    }

                    context_parts = [f"Document: {node_meta.get('title') or document_base_meta.get('title') or base_meta.get('title') or filename}"]
                    summary = node_meta.get("contextual_summary") or node_meta.get("section_summary") or node_meta.get("window")
                    if summary:
                        context_parts.append(str(summary))

                    context = " | ".join(part for part in context_parts if part)
                    nodes.append(
                        _create_node(
                            chunk_text,
                            document_base_meta,
                            chunk_meta,
                            context,
                            raw_node=raw_node,
                        )
                    )

            else:
                # Standard unstructured processing for other file types
                tracker.log_file_phase("Extracting content")
                whole_text = None
                # Try LlamaParse first for PDFs if enabled
                if ext == "pdf" and LLAMAPARSE_ENABLED:
                    tracker.log_file_phase("LlamaParse PDF extraction")
                    whole_text = _parse_pdf_with_llamaparse(path_str)
                    if not whole_text:
                        logger.warning("LlamaParse did not return content; falling back to Unstructured")

                # Fallback to Unstructured if no text yet
                if not whole_text:
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

                raw_nodes = build_nodes_from_text(whole_text, document_base_meta)
                total_file_chunks = len(raw_nodes)
                file_tokens = sum(len(raw_node.get_content().split()) for raw_node in raw_nodes)
                curr_offset = 0

                for idx, raw_node in enumerate(raw_nodes):
                    chunk_text = raw_node.get_content()
                    node_meta = dict(raw_node.metadata or {})
                    chunk_meta = {
                        **node_meta,
                        "chunk_index": idx,
                        "total_chunks": total_file_chunks,
                        "chunk_size": len(chunk_text),
                        "chunk_word_count": len(chunk_text.split()),
                    }

                    if is_transcript:
                        start_time_ts, end_time_ts, curr_offset = get_chunk_times(chunk_text, whole_text, offset_map, curr_offset)
                        duration = max(0, end_time_ts - start_time_ts)
                        chunk_meta.update({"start_time": start_time_ts, "end_time": end_time_ts, "duration": duration})

                    context_parts = [f"Document: {base_meta['title']}"]
                    summary = node_meta.get("section_summary") or node_meta.get("window")
                    if summary:
                        context_parts.append(str(summary))
                    if is_transcript and offset_map:
                        context_parts.append(f"Transcript segment ({start_time_ts:.1f}s-{end_time_ts:.1f}s)")
                    context = " | ".join(context_parts)
                    nodes.append(_create_node(chunk_text, document_base_meta, chunk_meta, context, raw_node=raw_node))

            chunk_count += total_file_chunks
            if processed_filenames is not None:
                processed_filenames.add(filename)
            tracker.log_file_complete(filename, total_file_chunks, file_tokens)

        except Exception as e:
            logger.warning(f"  │   └── ❌ Failed to process {filename}: {e}")
            if ext == "pdf":
                logger.error("  │       PDF processing failed - file may be corrupted, password-protected, or empty")
            continue

    # Enhanced summary logging
    total_tokens = sum(len(node.get_content().split()) for node in nodes)
    duration = time.time() - start_time

    logger.info(f"  └── ✅ Processed {len(nodes)} chunks, {total_tokens} tokens in {duration:.2f}s")

    # Update global tracker stats
    tracker.track_phase_stats("global", "chunks_created", chunk_count)
    tracker.track_phase_stats("global", "chunks_contextualized", len(nodes))
    tracker.track_phase_stats("global", "total_tokens", total_tokens)

    return nodes


__all__ = ["unstructured_loader"]
