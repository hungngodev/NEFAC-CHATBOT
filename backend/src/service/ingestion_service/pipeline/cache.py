"""
Cache and Docstore Utilities.

Factory functions for creating and managing:
- IngestionCache (transform caching)
- SimpleDocumentStore (document deduplication)
- Redis-backed caching (optional)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


def create_ingestion_cache(
    persist_dir: Optional[Union[str, Path]] = None,
    use_redis: bool = False,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> Any:
    """
    Create an IngestionCache for transform caching.

    Args:
        persist_dir: Optional directory for file-based persistence
        use_redis: Use Redis for distributed caching
        redis_host: Redis host (if use_redis=True)
        redis_port: Redis port (if use_redis=True)

    Returns:
        IngestionCache instance
    """
    try:
        from llama_index.core.ingestion import IngestionCache
    except ImportError:
        logger.warning("IngestionCache not available")
        return None

    if use_redis:
        try:
            from llama_index.storage.kvstore.redis import RedisKVStore

            redis_kvstore = RedisKVStore.from_host_and_port(redis_host, redis_port)
            cache = IngestionCache(cache=redis_kvstore)
            logger.info(f"Created Redis-backed IngestionCache ({redis_host}:{redis_port})")
            return cache
        except ImportError:
            logger.warning("Redis KVStore not available, falling back to in-memory")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, falling back to in-memory")

    cache = IngestionCache()
    logger.info("Created in-memory IngestionCache")
    return cache


def create_docstore(
    persist_path: Optional[Union[str, Path]] = None,
) -> Any:
    """
    Create a SimpleDocumentStore for document deduplication.

    Args:
        persist_path: Path to load existing docstore, or None for new

    Returns:
        SimpleDocumentStore instance
    """
    try:
        from llama_index.core.storage.docstore import SimpleDocumentStore
    except ImportError:
        logger.warning("SimpleDocumentStore not available")
        return None

    if persist_path:
        path = Path(persist_path)
        if path.exists():
            try:
                docstore = SimpleDocumentStore.from_persist_path(str(path))
                logger.info(f"Loaded docstore from {path}")
                return docstore
            except Exception as e:
                logger.warning(f"Failed to load docstore: {e}, creating new")

    docstore = SimpleDocumentStore()
    logger.info("Created new SimpleDocumentStore")
    return docstore


def save_pipeline_state(
    pipeline: Any,
    persist_dir: Union[str, Path],
    docstore: Optional[Any] = None,
) -> None:
    """
    Save pipeline and docstore state to disk.

    Args:
        pipeline: IngestionPipeline to persist
        persist_dir: Directory to save state
        docstore: Optional docstore to persist separately
    """
    save_dir = Path(persist_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Persist pipeline (includes cache)
    try:
        pipeline.persist(str(save_dir))
        logger.info(f"Saved pipeline state to {save_dir}")
    except Exception as e:
        logger.warning(f"Failed to persist pipeline: {e}")

    # Persist docstore
    if docstore:
        docstore_path = save_dir / "docstore.json"
        try:
            docstore.persist(str(docstore_path))
            logger.info(f"Saved docstore to {docstore_path}")
        except Exception as e:
            logger.warning(f"Failed to persist docstore: {e}")


def load_pipeline_state(
    persist_dir: Union[str, Path],
) -> Any:
    """
    Load pipeline state from disk.

    Args:
        persist_dir: Directory where state was saved

    Returns:
        Loaded IngestionPipeline
    """
    try:
        from llama_index.core.ingestion import IngestionPipeline
    except ImportError:
        logger.error("IngestionPipeline not available")
        return None

    try:
        # Create pipeline and load state in-place
        pipeline = IngestionPipeline(transformations=[])  # Minimal pipeline
        pipeline.load(str(persist_dir))  # type: ignore[arg-type]
        logger.info(f"Loaded pipeline from {persist_dir}")
        return pipeline
    except Exception as e:
        logger.error(f"Failed to load pipeline: {e}")
        raise
