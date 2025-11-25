import logging
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from load_env import load_env as load_env_from_root
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from src.config.models import EMBEEDING_MODEL_NAME

# Load env using shared helper (supports ENV_FILE override, repo root, cwd search)
load_env_from_root()

logger = logging.getLogger(__name__)


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Embedding / LLM configuration with graceful fallbacks
# ---------------------------------------------------------------------------

openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key:
    embedding_model = OpenAIEmbedding(model=EMBEEDING_MODEL_NAME, api_key=openai_api_key)
    Settings.embed_model = embedding_model
else:
    embedding_model = None
    logger.warning("OPENAI_API_KEY is not set; default LlamaIndex embedding configuration will be used.")

llm_model_name = os.getenv("INGESTION_LLM_MODEL", "gpt-4o-mini")
if openai_api_key:
    llm_model = OpenAI(
        model=llm_model_name,
        timeout=_get_env_float("INGESTION_LLM_TIMEOUT", 60.0),
        max_retries=_get_env_int("INGESTION_LLM_MAX_RETRIES", 3),
    )
    Settings.llm = llm_model
else:
    llm_model = None
    logger.warning("OPENAI_API_KEY missing; ingestion LLM disabled. Set the key to enable contextual retrieval " "(see https://developers.llamaindex.ai/python/examples/cookbooks/contextual_retrieval/).")

graph_llm_model_name = os.getenv("GRAPH_LLM_MODEL", "gpt-4o")
if openai_api_key:
    graph_llm_model = OpenAI(
        model=graph_llm_model_name,
        timeout=_get_env_float("GRAPH_LLM_TIMEOUT", 150.0),
        max_retries=_get_env_int("GRAPH_LLM_MAX_RETRIES", 2),
    )
else:
    graph_llm_model = None
    logger.warning("Graph LLM disabled because OPENAI_API_KEY is not set. Property graph ingestion " "(https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/) " "will fall back to schema-free mode.")

# ---------------------------------------------------------------------------
# Feature toggles surfaced via environment variables for discoverability
# ---------------------------------------------------------------------------

ENABLE_CONTEXTUAL_RETRIEVAL = _get_env_bool("ENABLE_CONTEXTUAL_RETRIEVAL", True)
ENABLE_METADATA_EXTRACTION = _get_env_bool("ENABLE_METADATA_EXTRACTION", False)

# Embedding model dimensions
# Based on: https://platform.openai.com/docs/guides/embeddings
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_EMBED_MODEL_DIM = _get_env_int("OPENAI_EMBED_MODEL_DIM", 1536)  # text-embedding-3-small

# Hybrid retriever defaults inspired by the multi-doc tutorial
# https://developers.llamaindex.ai/python/examples/retrievers/multi_doc_together_hybrid/
HYBRID_FUSION_STRATEGY = os.getenv("HYBRID_FUSION_STRATEGY", "rrf").lower()
HYBRID_DENSE_WEIGHT = _get_env_float("HYBRID_DENSE_WEIGHT", 1.0)
HYBRID_SPARSE_WEIGHT = _get_env_float("HYBRID_SPARSE_WEIGHT", 0.75)
HYBRID_GRAPH_WEIGHT = _get_env_float("HYBRID_GRAPH_WEIGHT", 0.5)
HYBRID_RRF_K = _get_env_float("HYBRID_RRF_K", 60.0)
HYBRID_MIN_SCORE = _get_env_float("HYBRID_MIN_SCORE", 0.0)
HYBRID_RERANK_MODEL = os.getenv("HYBRID_RERANK_MODEL", "rerank-english-v3.0")
HYBRID_WEIGHTS: Dict[str, float] = {
    "dense": HYBRID_DENSE_WEIGHT,
    "sparse": HYBRID_SPARSE_WEIGHT,
    "graph": HYBRID_GRAPH_WEIGHT,
}

GRAPH_MODE = os.getenv("GRAPH_MODE", os.getenv("GRAPH_LI_MODE", "property")).lower()

# Elasticsearch ingestion strategy configuration
# Based on: https://www.elastic.co/search-labs/blog/elasticsearch-llamaindex-ingest-data
ELASTICSEARCH_STRATEGY = os.getenv("ELASTICSEARCH_STRATEGY", "hybrid")  # dense | bm25 | sparse | hybrid
ELASTICSEARCH_BATCH_SIZE = _get_env_int("ELASTICSEARCH_BATCH_SIZE", 100)

# Qdrant ingestion configuration with hybrid search
# Based on: https://developers.llamaindex.ai/python/examples/vector_stores/qdrant_hybrid/
QDRANT_SPARSE_TOP_K = _get_env_int("QDRANT_SPARSE_TOP_K", 100)
QDRANT_HYBRID_ALPHA = _get_env_float("QDRANT_HYBRID_ALPHA", 0.5)  # Balance between dense (1.0) and sparse (0.0)
QDRANT_FUSION_ALGORITHM = os.getenv("QDRANT_FUSION_ALGORITHM", "relative_score")  # relative_score | rrf

# Neo4j Property Graph ingestion configuration
# Based on: https://developers.llamaindex.ai/python/examples/property_graph/property_graph_neo4j/
GRAPH_ENABLE_ENTITY_DEDUPLICATION = _get_env_bool("GRAPH_ENABLE_ENTITY_DEDUPLICATION", True)
GRAPH_ENTITY_SIMILARITY_THRESHOLD = _get_env_float("GRAPH_ENTITY_SIMILARITY_THRESHOLD", 0.9)
GRAPH_USE_WORD_DISTANCE = _get_env_bool("GRAPH_USE_WORD_DISTANCE", True)
GRAPH_WORD_DISTANCE_THRESHOLD = _get_env_int("GRAPH_WORD_DISTANCE_THRESHOLD", 2)
GRAPH_MAX_TRIPLETS_PER_CHUNK = _get_env_int("GRAPH_MAX_TRIPLETS_PER_CHUNK", 20)
GRAPH_NUM_WORKERS = _get_env_int("GRAPH_NUM_WORKERS", 4)

# Workflow retry and fallback configuration
# Based on: https://www.elastic.co/search-labs/blog/llamaindex-workflows-with-elasticsearch
WORKFLOW_MAX_RETRIES = _get_env_int("WORKFLOW_MAX_RETRIES", 3)
WORKFLOW_ENABLE_MODEL_FALLBACK = _get_env_bool("WORKFLOW_ENABLE_MODEL_FALLBACK", True)
WORKFLOW_FALLBACK_MODEL = os.getenv("WORKFLOW_FALLBACK_MODEL", "gpt-3.5-turbo")
WORKFLOW_ENABLE_VALIDATION = _get_env_bool("WORKFLOW_ENABLE_VALIDATION", True)

# Semantic splitter language configuration
# Based on: https://developers.llamaindex.ai/python/examples/node_parsers/semantic_double_merging_chunking/
SEMANTIC_SPLITTER_LANGUAGE = os.getenv("SEMANTIC_SPLITTER_LANGUAGE", "english")
SEMANTIC_SPLITTER_AUTO_DOWNLOAD = _get_env_bool("SEMANTIC_SPLITTER_AUTO_DOWNLOAD", True)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    logger.info("COHERE_API_KEY not provided; Cohere reranking remains optional until configured.")

LLM_MODEL_NAME = llm_model_name
GRAPH_LLM_MODEL_NAME = graph_llm_model_name
CHUNK_SIZE = 320
CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
