"""Metadata helpers used by the ingestion workflow."""

from __future__ import annotations

import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _get_base_metadata(path: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    stat = os.stat(path)
    base_name = os.path.basename(path)
    title = entry.get("title") or os.path.splitext(base_name)[0]
    abs_path = os.path.abspath(path)

    def to_iso(ts: float) -> str:
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
        "file_extension": Path(path).suffix.lower().lstrip("."),
        "source": entry.get("source") or title,
        "slug": entry.get("slug") or base_name.replace(" ", "-").lower(),
        "uri": entry.get("uri") or f"file://{abs_path}",
        "link": entry.get("link") or f"file://{abs_path}",
        "processing_timestamp": time.time(),
    }


__all__ = ["_get_base_metadata"]
