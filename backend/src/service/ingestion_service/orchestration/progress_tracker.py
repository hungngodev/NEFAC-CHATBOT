from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class FailureRecord:
    file_type: str
    filename: str
    phase: str
    error: str
    attempts: int = 0
    last_timestamp: float = 0.0


class PipelineTracker:
    def __init__(self):
        self.stats = defaultdict(lambda: defaultdict(int))
        self.model_usage = {}
        self.start_time = time.time()
        self._phase_times = {}
        self._current_file = None
        self._failures: Dict[Tuple[str, str], FailureRecord] = {}

    def log_phase_start(self, phase: str):
        self._phase_times[phase] = time.time()

    def log_phase_end(self, phase: str):
        if phase in self._phase_times:
            time.time() - self._phase_times[phase]

    def log_file_start(self, file_type: str, filename: str, index: int, total: int):
        self._current_file = filename
        self.stats[file_type]["files_loaded"] += 1

    def log_file_phase(self, phase: str, count: Optional[int] = None, model_name: Optional[str] = None):
        parts = [f"  │   ├── {phase}"]
        if count is not None:
            parts.append(f": {count} items")
        if model_name:
            parts.append(f" (🧠 {model_name})")
            self.model_usage[phase] = model_name

    def log_file_complete(self, filename: str, chunks: int, tokens: int):
        if self._current_file == filename:
            self._current_file = None

    def log_pipeline_step(self, message: str, model_name: Optional[str] = None):
        if model_name:
            self.model_usage[message] = model_name
        else:

            pass

    def track_db_upload(self, file_type: str, db_name: str, count: int):
        self.stats[file_type][f"{db_name.lower()}_uploaded"] += count

    def track_phase_stats(self, file_type: str, phase: str, count: int):
        self.stats[file_type][phase] += count

    def log_summary(self):
        time.time() - self.start_time

        for file_type, phases in self.stats.items():
            if phases.get("files_loaded", 0) > 0:
                [
                    f"  Files Processed: {phases.get('files_loaded', 0)}",
                    f"  Files Skipped: {phases.get('files_skipped', 0)}",
                    f"  Chunks Created: {phases.get('chunks_created', 0)}",
                    f"  Chunks Contextualized: {phases.get('chunks_contextualized', 0)}",
                    f"  Uploaded to Qdrant: {phases.get('qdrant_uploaded', 0)}",
                    f"  Uploaded to Elasticsearch: {phases.get('elasticsearch_uploaded', 0)}",
                    f"  Uploaded to Neo4j: {phases.get('neo4j_uploaded', 0)}",
                ]

        if self.model_usage:
            for phase, model in self.model_usage.items():

                pass
        if self._failures:
            for record in self._failures.values():

                pass

    def record_failure(self, file_type: str, filename: str, phase: str, error: Exception | str):
        key = (file_type, filename)
        message = str(error)
        record = self._failures.get(key)
        if record is None:
            record = FailureRecord(
                file_type=file_type,
                filename=filename,
                phase=phase,
                error=message,
                attempts=0,
            )
            self._failures[key] = record

        record.attempts += 1
        record.phase = phase
        record.error = message
        record.last_timestamp = time.time()

    def mark_success(self, file_type: str, filename: str):
        key = (file_type, filename)
        if key in self._failures:
            del self._failures[key]

    def export_failures(self, output_path: Path) -> None:
        if not self._failures:
            if output_path.exists():
                output_path.unlink()
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialised: List[dict] = [asdict(record) for record in self._failures.values()]
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(serialised, handle, indent=2)

    def pending_failures(self) -> List[FailureRecord]:
        return list(self._failures.values())

    def seed_failures(self, failures: Iterable[FailureRecord]) -> None:
        for record in failures:
            key = (record.file_type, record.filename)
            self._failures[key] = record

    @staticmethod
    def load_failures(input_path: Path) -> List[FailureRecord]:
        if not input_path.exists():
            return []

        with input_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        failures: List[FailureRecord] = []
        for entry in raw:
            try:
                failures.append(FailureRecord(**entry))
            except TypeError:
                continue
        return failures


_global_tracker = None


def get_tracker() -> PipelineTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PipelineTracker()
    return _global_tracker


def reset_tracker():
    global _global_tracker
    _global_tracker = PipelineTracker()
