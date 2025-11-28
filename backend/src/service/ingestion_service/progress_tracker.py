from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)


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
        logger.info(f"🚀 {phase}")
        self._phase_times[phase] = time.time()

    def log_phase_end(self, phase: str):
        if phase in self._phase_times:
            duration = time.time() - self._phase_times[phase]
            logger.info(f"✅ {phase} completed in {duration:.2f}s")

    def log_file_start(self, file_type: str, filename: str, index: int, total: int):
        self._current_file = filename
        logger.info(f"  ├── [{index}/{total}] {filename}")
        self.stats[file_type]["files_loaded"] += 1

    def log_file_phase(self, phase: str, count: int = None, model_name: str = None):
        parts = [f"  │   ├── {phase}"]
        if count is not None:
            parts.append(f": {count} items")
        if model_name:
            parts.append(f" (🧠 {model_name})")
            self.model_usage[phase] = model_name
        logger.info("".join(parts))

    def log_file_complete(self, filename: str, chunks: int, tokens: int):
        logger.info(f"  │   └── ✅ {chunks} chunks, {tokens} tokens")
        if self._current_file == filename:
            self._current_file = None

    def log_pipeline_step(self, message: str, model_name: str = None):
        if model_name:
            logger.info(f"  ➡️ {message} (🧠 {model_name})")
            self.model_usage[message] = model_name
        else:
            logger.info(f"  ➡️ {message}")

    def track_db_upload(self, file_type: str, db_name: str, count: int):
        logger.info(f"  │   └── {db_name}: {count} items uploaded")
        self.stats[file_type][f"{db_name.lower()}_uploaded"] += count

    def track_phase_stats(self, file_type: str, phase: str, count: int):
        self.stats[file_type][phase] += count

    def log_summary(self):
        total_duration = time.time() - self.start_time
        separator = "=" * 80
        logger.info(f"\n{separator}")
        logger.info("📊 INGESTION PIPELINE SUMMARY")
        logger.info(separator)
        logger.info(f"⏱️ Total execution time: {total_duration:.2f}s")

        for file_type, phases in self.stats.items():
            if phases.get("files_loaded", 0) > 0:
                logger.info(f"\n📁 {file_type.upper()}")
                stats = [
                    f"  Files Processed: {phases.get('files_loaded', 0)}",
                    f"  Chunks Created: {phases.get('chunks_created', 0)}",
                    f"  Chunks Contextualized: {phases.get('chunks_contextualized', 0)}",
                    f"  Uploaded to Qdrant: {phases.get('qdrant_uploaded', 0)}",
                    f"  Uploaded to Elasticsearch: {phases.get('elasticsearch_uploaded', 0)}",
                    f"  Uploaded to Neo4j: {phases.get('neo4j_uploaded', 0)}",
                ]
                logger.info("\n".join(stats))

        if self.model_usage:
            logger.info("\n🤖 MODELS USED")
            for phase, model in self.model_usage.items():
                logger.info(f"  {phase}: {model}")

        if self._failures:
            logger.info("\n⚠️ PENDING FAILURES")
            for record in self._failures.values():
                logger.info(
                    "  %s/%s -> phase=%s, attempts=%d, last_error=%s",
                    record.file_type,
                    record.filename,
                    record.phase,
                    record.attempts,
                    record.error,
                )

        logger.info(separator)

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
