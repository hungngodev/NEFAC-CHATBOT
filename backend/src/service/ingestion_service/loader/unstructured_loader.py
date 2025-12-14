import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode, TextNode
from unstructured.partition.auto import partition as u_partition

from src.service.ingestion_service import settings as ingestion_settings
from src.service.ingestion_service.llamaindex.metadata_utils import _get_base_metadata
from src.service.ingestion_service.llamaindex.node_parser import build_nodes_from_text
from src.service.ingestion_service.loader.spreadsheet_utils import process_xlsx_intelligently

TRANSCRIPT_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")

CONTEXT_FORMAT = getattr(
    ingestion_settings,
    "CONTEXT_FORMAT",
    "Context: {context}\n\nChunk: {chunk}",
)


def parse_timestamps(transcript_text: str) -> Tuple[str, List[Dict[str, Any]]]:
    segments: List[Dict[str, Any]] = []
    clean_text = ""
    offset_map: List[Dict[str, Any]] = []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = TRANSCRIPT_PATTERN.match(line)
        if match:
            ts_str, text = match.groups()
            parts = ts_str.split(":")
            try:
                seconds: float
                if len(parts) == 1:
                    seconds = float(parts[0])
                elif len(parts) == 2:
                    seconds = int(parts[0]) * 60 + float(parts[1])
                else:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                if text.strip():
                    segments.append({"start": seconds, "text": text.strip()})
            except ValueError:
                continue
        elif segments:
            prev_text = str(segments[-1]["text"])
            segments[-1]["text"] = prev_text + " " + line

    for i, seg in enumerate(segments):
        start_char = len(clean_text)
        separator = "\n"
        seg_start: float = float(seg["start"])
        seg_text: str = str(seg["text"])

        if i + 1 < len(segments):
            next_start: float = float(segments[i + 1]["start"])
            time_diff = next_start - seg_start
            probability = min(1.0, max(0.0, (time_diff - 0.5) / 2.0))
            rand_val = int(hashlib.md5(seg_text.encode()).hexdigest(), 16) % 1000 / 1000.0

            if rand_val < probability:
                separator = "\n\n"

        clean_text += seg_text + separator
        end_char = len(clean_text) - 1
        end_time = float(segments[i + 1]["start"]) if i + 1 < len(segments) else None
        offset_map.append({"start_char": start_char, "end_char": end_char, "start_time": seg_start, "end_time": end_time})

    return clean_text.strip(), offset_map


def get_chunk_times(chunk_text: str, full_text: str, offset_map: Optional[List[Dict[str, Any]]], curr_offset: int) -> Tuple[float, float, int]:
    start = max(full_text.find(chunk_text, curr_offset), curr_offset)
    end = start + len(chunk_text)
    start_time = end_time = 0.0

    if offset_map:
        start_time = next(
            (float(seg["start_time"]) for seg in offset_map if seg["start_char"] <= start <= seg["end_char"]),
            0.0,
        )
        end_time = next(
            (float(seg["end_time"] or start_time) for seg in reversed(offset_map) if seg["start_char"] <= end <= seg["end_char"]),
            start_time,
        )

    return start_time, end_time, end


def _create_node(
    chunk_text: str,
    base_meta: Dict[str, Any],
    chunk_meta: Dict[str, Any],
    context: str,
    raw_node: Optional[BaseNode] = None,
) -> TextNode:
    metadata = {**base_meta, **chunk_meta}
    metadata["id"] = raw_node.node_id if raw_node is not None else metadata.get("id")
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
    node.excluded_embed_metadata_keys.extend(ingestion_settings.EXCLUDED_METADATA_KEYS)
    node.excluded_llm_metadata_keys.extend(ingestion_settings.EXCLUDED_METADATA_KEYS)
    return node


__all__ = ["load_document_nodes"]


def load_document_nodes(
    file_path: str | Path,
    entry: Dict[str, Any],
    *,
    tracker=None,
    file_type: Optional[str] = None,
) -> Tuple[List[TextNode], int, int]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    path_str = str(path)
    ext = path.suffix.lower().lstrip(".")
    supported_exts = {"pdf", "html", "htm", "xlsx", "xls", "txt", "docx", "doc", "pptx", "ppt", "csv"}
    if ext not in supported_exts:
        raise ValueError(f"Unsupported file extension: .{ext}")

    base_meta = _get_base_metadata(path_str, entry)
    document_base_meta = base_meta.copy()
    document_base_meta.update({k: v for k, v in (entry or {}).items() if v is not None})

    nodes: List[TextNode] = []
    total_file_chunks = 0
    file_tokens = 0

    def _log_phase(message: str) -> None:
        if tracker is not None:
            tracker.log_file_phase(message)
        else:

            pass

    try:
        if ext in {"xlsx", "xls", "csv"}:
            _log_phase("Parsing spreadsheet structure")
            xlsx_chunks = process_xlsx_intelligently(str(path), entry)

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

        else:
            _log_phase("Extracting content")
            whole_text = None

            is_transcript = False
            offset_map = None

            if not whole_text:
                if ext == "txt":
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            whole_text = f.read()
                    except Exception:

                        pass
                if not whole_text:
                    elements = u_partition(path_str)
                    whole_text = "\n\n".join(str(el).strip() for el in elements if str(el).strip())

                    if ext in {"html", "pdf"}:

                        pass
            if ext == "txt":
                elem_info = len(elements) if "elements" in locals() else "1 (Direct)"

                _log_phase("Parsing transcript timestamps")
                clean_text, offset_map = parse_timestamps(whole_text)

                if clean_text.strip():
                    is_transcript = True
                    base_meta.update({"transcript_type": "youtube", "has_timestamps": True})
                    whole_text = clean_text
                else:
                    first_lines = whole_text[:500].splitlines()
                    for i, line in enumerate(first_lines[:5]):

                        pass
                    if len(whole_text) > 1000 and whole_text.count("\n") < len(whole_text) / 200:
                        pre_splitter = SentenceSplitter(chunk_size=200, chunk_overlap=0)
                        text_chunks = pre_splitter.split_text(whole_text)
                        whole_text = "\n\n".join(text_chunks)

            if not whole_text or not whole_text.strip():
                return [], 0, 0

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

                if is_transcript and offset_map:
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

        return nodes, total_file_chunks, file_tokens

    except Exception:
        raise
