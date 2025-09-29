import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

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


embedding_model = OpenAIEmbeddings(model=EMBEEDING_MODEL_NAME)

llm_model = ChatOpenAI(
    model="gpt-5-nano",
    disable_streaming=True,
    timeout=_get_env_float("INGESTION_LLM_TIMEOUT", 60.0),
    max_retries=_get_env_int("INGESTION_LLM_MAX_RETRIES", 3),
)

# llm_model = ChatOllama(model = "llama3.3:70b")
# llm_model = ChatOllama(model="alibayram/Qwen3-30B-A3B-Instruct-2507:latest")
# graph_llm_model = ChatOllama(model="llama3.3:70b")
graph_llm_model = ChatOpenAI(
    model="gpt-5-mini",
    disable_streaming=True,
    timeout=_get_env_float("GRAPH_LLM_TIMEOUT", 150.0),
    max_retries=_get_env_int("GRAPH_LLM_MAX_RETRIES", 2),
)
# embedding_model = OllamaEmbeddings(model="dengcao/Qwen3-Embedding-8B:Q5_K_M")
CHUNK_SIZE = 320
CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
