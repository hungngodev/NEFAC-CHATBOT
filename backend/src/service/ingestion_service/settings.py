import os

from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

from src.config.models import EMBEEDING_MODEL_NAME

load_dotenv()


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


embedding_model = OpenAIEmbedding(model=EMBEEDING_MODEL_NAME, api_key=os.getenv("OPENAI_API_KEY"))
Settings.embed_model = embedding_model

llm_model_name = os.getenv("INGESTION_LLM_MODEL", "gpt-4o-mini")
llm_model = OpenAI(
    model=llm_model_name,
    timeout=_get_env_float("INGESTION_LLM_TIMEOUT", 60.0),
    max_retries=_get_env_int("INGESTION_LLM_MAX_RETRIES", 3),
)
Settings.llm = llm_model

graph_llm_model_name = os.getenv("GRAPH_LLM_MODEL", "gpt-4o")
graph_llm_model = OpenAI(
    model=graph_llm_model_name,
    timeout=_get_env_float("GRAPH_LLM_TIMEOUT", 150.0),
    max_retries=_get_env_int("GRAPH_LLM_MAX_RETRIES", 2),
)

LLM_MODEL_NAME = llm_model_name
GRAPH_LLM_MODEL_NAME = graph_llm_model_name
CHUNK_SIZE = 320
CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
