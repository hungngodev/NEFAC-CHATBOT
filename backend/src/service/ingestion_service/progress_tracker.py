from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


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
        self.model_usage: Dict[str, str] = {}
        self.start_time = time.time()
        self._phase_times: Dict[str, float] = {}
        self._current_file: str | None = None
        self._failures: Dict[Tuple[str, str], FailureRecord] = {}

    def log_phase_start(self, phase: str):
        self._phase_times[phase] = time.time()

    def log_phase_end(self, phase: str):
        pass

    def log_file_start(self, file_type: str, filename: str, index: int, total: int):
        self._current_file = filename
        self.stats[file_type]["files_loaded"] += 1

    def log_file_phase(self, phase: str, count: int | None = None, model_name: str | None = None):
        if model_name:
            self.model_usage[phase] = model_name

    def log_file_complete(self, filename: str, chunks: int, tokens: int):
        if self._current_file == filename:
            self._current_file = None

    def log_pipeline_step(self, message: str, model_name: str | None = None):
        if model_name:
            self.model_usage[message] = model_name

    def track_db_upload(self, file_type: str, db_name: str, count: int):
        self.stats[file_type][f"{db_name.lower()}_uploaded"] += count

    def track_phase_stats(self, file_type: str, phase: str, count: int):
        self.stats[file_type][phase] += count

    def log_summary(self):
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
        self._failures.pop(key, None)

    def export_failures(self, output_path: Path) -> None:
        if not self._failures:
            if output_path.exists():
                output_path.unlink()
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialised = [asdict(record) for record in self._failures.values()]
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


_global_tracker: PipelineTracker | None = None


def get_tracker() -> PipelineTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PipelineTracker()
    return _global_tracker


def reset_tracker():
    global _global_tracker
    _global_tracker = PipelineTracker()
