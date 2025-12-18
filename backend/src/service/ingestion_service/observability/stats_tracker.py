"""
Ingestion Stats Tracker.

Systematic tracking of document processing status, failures, and statistics.
Provides per-document error tracking and final summary reporting.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class DocumentStatus:
    """Status of a single document in the ingestion pipeline."""

    doc_id: str
    file_path: str
    status: Literal["pending", "processing", "success", "failed", "skipped"]
    current_stage: str
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def duration_seconds(self) -> float:
        """Get processing duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


@dataclass
class StageStats:
    """Statistics for a pipeline stage."""

    name: str
    started: int = 0
    completed: int = 0
    failed: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration_seconds(self) -> float:
        """Get stage duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0


@dataclass
class IngestionSummary:
    """Summary of ingestion run."""

    total_documents: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_seconds: float = 0.0
    stage_stats: Dict[str, StageStats] = field(default_factory=dict)
    failed_documents: List[Dict[str, Any]] = field(default_factory=list)


class IngestionStatsTracker:
    """
    Systematic tracking of document processing and failures.

    Thread-safe tracker that records:
    - Per-document status and errors
    - Pipeline stage statistics
    - Final summary with success/failure counts

    Usage:
        tracker = IngestionStatsTracker()
        tracker.start_document("doc1", "/path/to/file.pdf")
        try:
            # process document
            tracker.complete_document("doc1", "embedding")
        except Exception as e:
            tracker.fail_document("doc1", "embedding", str(e))

        tracker.print_summary()
    """

    def __init__(self) -> None:
        self._documents: Dict[str, DocumentStatus] = {}
        self._stages: Dict[str, StageStats] = {}
        self._lock = threading.RLock()
        self._start_time = time.time()
        self._end_time: Optional[float] = None

    def start_document(self, doc_id: str, file_path: str, stage: str = "loading") -> None:
        """Mark a document as started processing."""
        with self._lock:
            self._documents[doc_id] = DocumentStatus(
                doc_id=doc_id,
                file_path=file_path,
                status="processing",
                current_stage=stage,
            )

    def update_document_stage(self, doc_id: str, stage: str) -> None:
        """Update the current stage of a document."""
        with self._lock:
            if doc_id in self._documents:
                self._documents[doc_id].current_stage = stage

    def complete_document(self, doc_id: str, final_stage: str = "complete") -> None:
        """Mark a document as successfully completed."""
        with self._lock:
            if doc_id in self._documents:
                doc = self._documents[doc_id]
                doc.status = "success"
                doc.current_stage = final_stage
                doc.end_time = time.time()

    def fail_document(self, doc_id: str, stage: str, error: str) -> None:
        """Mark a document as failed with error details."""
        with self._lock:
            if doc_id in self._documents:
                doc = self._documents[doc_id]
                doc.status = "failed"
                doc.current_stage = stage
                doc.error = error
                doc.end_time = time.time()
            else:
                self._documents[doc_id] = DocumentStatus(
                    doc_id=doc_id,
                    file_path="unknown",
                    status="failed",
                    current_stage=stage,
                    error=error,
                    end_time=time.time(),
                )

    def skip_document(self, doc_id: str, reason: str, file_path: str = "unknown") -> None:
        """Mark a document as skipped."""
        with self._lock:
            self._documents[doc_id] = DocumentStatus(
                doc_id=doc_id,
                file_path=file_path,
                status="skipped",
                current_stage="skipped",
                error=reason,
                end_time=time.time(),
            )

    def start_stage(self, stage_name: str) -> None:
        """Mark a pipeline stage as started."""
        with self._lock:
            if stage_name not in self._stages:
                self._stages[stage_name] = StageStats(name=stage_name)
            self._stages[stage_name].start_time = time.time()
            self._stages[stage_name].started += 1

    def complete_stage(self, stage_name: str, items_processed: int = 0) -> None:
        """Mark a pipeline stage as completed."""
        with self._lock:
            if stage_name not in self._stages:
                self._stages[stage_name] = StageStats(name=stage_name)
            stage = self._stages[stage_name]
            stage.end_time = time.time()
            stage.completed += items_processed

    def fail_stage(self, stage_name: str, error: str) -> None:
        """Record a stage failure."""
        with self._lock:
            if stage_name not in self._stages:
                self._stages[stage_name] = StageStats(name=stage_name)
            self._stages[stage_name].failed += 1
            self._stages[stage_name].end_time = time.time()

    def get_summary(self) -> IngestionSummary:
        """Get complete ingestion summary."""
        with self._lock:
            summary = IngestionSummary()
            summary.total_documents = len(self._documents)

            for doc in self._documents.values():
                if doc.status == "success":
                    summary.successful += 1
                elif doc.status == "failed":
                    summary.failed += 1
                    summary.failed_documents.append(
                        {
                            "doc_id": doc.doc_id,
                            "file_path": doc.file_path,
                            "stage": doc.current_stage,
                            "error": doc.error,
                            "duration": doc.duration_seconds,
                        }
                    )
                elif doc.status == "skipped":
                    summary.skipped += 1

            summary.stage_stats = {name: stats for name, stats in self._stages.items()}
            summary.total_duration_seconds = (self._end_time or time.time()) - self._start_time

            return summary

    def get_failed_documents(self) -> List[DocumentStatus]:
        """Get list of all failed documents."""
        with self._lock:
            return [doc for doc in self._documents.values() if doc.status == "failed"]

    def finalize(self) -> None:
        """Mark the ingestion run as complete."""
        with self._lock:
            self._end_time = time.time()

    def print_summary(self) -> None:
        """Print a formatted summary of the ingestion run."""
        self.finalize()
        self.get_summary()

    def reset(self) -> None:
        """Reset all tracking data."""
        with self._lock:
            self._documents.clear()
            self._stages.clear()
            self._start_time = time.time()
            self._end_time = None

    def to_dict(self) -> Dict[str, Any]:
        """Export tracker state as dictionary."""
        summary = self.get_summary()
        return asdict(summary)


_global_tracker: Optional[IngestionStatsTracker] = None


def get_stats_tracker() -> IngestionStatsTracker:
    """Get or create the global stats tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = IngestionStatsTracker()
    return _global_tracker


def reset_stats_tracker() -> None:
    """Reset the global stats tracker."""
    global _global_tracker
    if _global_tracker:
        _global_tracker.reset()
    _global_tracker = IngestionStatsTracker()
