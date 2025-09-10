"""
Systematic Progress Tracker for Document Ingestion Pipeline
Provides clean, tree-like progress tracking with detailed statistics.
"""

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class PipelineTracker:
    """Clean, systematic progress tracking with tree-like indentation and detailed stats."""

    def __init__(self):
        self.stats = defaultdict(lambda: defaultdict(int))
        self.model_usage = {}
        self.start_time = time.time()
        self._phase_times = {}
        self._current_file = None

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

        # Summary by file type
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

        # Model usage summary
        if self.model_usage:
            logger.info("\n🤖 MODELS USED")
            for phase, model in self.model_usage.items():
                logger.info(f"  {phase}: {model}")

        logger.info(separator)


_global_tracker = None


def get_tracker() -> PipelineTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PipelineTracker()
    return _global_tracker


def reset_tracker():
    global _global_tracker
    _global_tracker = PipelineTracker()
