from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union


def create_ingestion_cache(
    persist_dir: Optional[Union[str, Path]] = None,
    use_redis: bool = False,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> Any:
    try:
        from llama_index.core.ingestion import IngestionCache
    except ImportError:
        return None

    if use_redis:
        try:
            from llama_index.storage.kvstore.redis import RedisKVStore

            redis_kvstore = RedisKVStore.from_host_and_port(redis_host, redis_port)
            cache = IngestionCache(cache=redis_kvstore)
            return cache
        except ImportError:
            pass
        except Exception:

            pass
    cache = IngestionCache()
    return cache


def create_docstore(
    persist_path: Optional[Union[str, Path]] = None,
) -> Any:
    try:
        from llama_index.core.storage.docstore import SimpleDocumentStore
    except ImportError:
        return None

    if persist_path:
        path = Path(persist_path)
        if path.exists():
            try:
                docstore = SimpleDocumentStore.from_persist_path(str(path))
                return docstore
            except Exception:

                pass
    docstore = SimpleDocumentStore()
    return docstore


def save_pipeline_state(
    pipeline: Any,
    persist_dir: Union[str, Path],
    docstore: Optional[Any] = None,
) -> None:
    save_dir = Path(persist_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        pipeline.persist(str(save_dir))
    except Exception:

        pass
    if docstore:
        docstore_path = save_dir / "docstore.json"
        try:
            docstore.persist(str(docstore_path))
        except Exception:

            pass


def load_pipeline_state(
    persist_dir: Union[str, Path],
) -> Any:
    try:
        from llama_index.core.ingestion import IngestionPipeline
    except ImportError:
        return None

    try:
        pipeline = IngestionPipeline(transformations=[])
        pipeline.load(str(persist_dir))  # type: ignore[arg-type]
        return pipeline
    except Exception:
        raise
