from __future__ import annotations

import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

MAX_STRING_LEN = 512


def _get_base_metadata(path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    stat = os.stat(path)
    base_name = os.path.basename(path)
    title = entry.get("title") or os.path.splitext(base_name)[0]
    abs_path = os.path.abspath(path)

    def to_iso(ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    source_url = entry.get("source_url") or entry.get("link") or f"file://{abs_path}"
    date_val = entry.get("date") or to_iso(getattr(stat, "st_ctime", stat.st_mtime))

    return {
        "id": entry.get("id") or entry.get("graphql_id") or base_name,
        "title": title,
        "filename": base_name,
        "source_url": source_url,
        "date": date_val,
        "modified": entry.get("modified") or to_iso(stat.st_mtime),
        "mime_type": entry.get("mime_type") or mimetypes.guess_type(base_name)[0],
        "file_size": entry.get("file_size") or stat.st_size,
        "file_path": entry.get("file_path") or abs_path,
        "file_extension": Path(path).suffix.lower().lstrip("."),
        "source": entry.get("source") or title,
        "slug": entry.get("slug") or base_name.replace(" ", "-").lower(),
        "uri": entry.get("uri") or f"file://{abs_path}",
        "link": entry.get("link") or f"file://{abs_path}",
        "processing_timestamp": time.time(),
    }


def build_chunk_id(doc_id: Optional[str], chunk_index: Optional[int]) -> Optional[str]:
    if doc_id is None or chunk_index is None:
        return None
    return f"{doc_id}::chunk-{int(chunk_index):04d}"


def _truncate(value: str) -> str:
    return value if len(value) <= MAX_STRING_LEN else value[:MAX_STRING_LEN]


def sanitize_metadata(
    meta: Dict[str, Any],
    include_text: bool = False,
    keep_summary: bool = False,
) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in meta.items():
        if key.startswith("_") or key == "relationships":
            continue
        if isinstance(value, (str, int, float, bool)):
            if key == "contextual_summary" and not keep_summary:
                continue
            cleaned[key] = _truncate(value) if isinstance(value, str) else value
        elif isinstance(value, list):
            items: list[str] = []
            for item in value:
                if isinstance(item, str):
                    items.append(_truncate(item))
                elif isinstance(item, (int, float, bool)):
                    items.append(str(item))
            if items:
                cleaned[key] = items
        elif isinstance(value, dict):
            sub: dict[str, Any] = {}
            for k, v in value.items():
                if isinstance(v, str):
                    sub[k] = _truncate(v)
                elif isinstance(v, (int, float, bool)):
                    sub[k] = v
            if sub:
                cleaned[key] = sub
    doc_id_val = cleaned.get("doc_id")
    chunk_index_val = cleaned.get("chunk_index")
    chunk_id = cleaned.get("chunk_id") or build_chunk_id(str(doc_id_val) if doc_id_val is not None else None, int(chunk_index_val) if isinstance(chunk_index_val, (int, float)) else None)
    if chunk_id:
        cleaned.setdefault("chunk_id", chunk_id)
    if "id" not in cleaned and chunk_id:
        cleaned["id"] = chunk_id
    if include_text and "text" in meta and isinstance(meta["text"], str):
        cleaned["text"] = meta["text"]

    for field in ["section_summary", "questions_this_excerpt_can_answer", "excerpt_keywords"]:
        if field in meta and isinstance(meta[field], str):
            cleaned[field] = meta[field]

    return cleaned


__all__ = ["_get_base_metadata", "build_chunk_id", "sanitize_metadata"]
