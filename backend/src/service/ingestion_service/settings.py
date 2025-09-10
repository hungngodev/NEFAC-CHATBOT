from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from src.config.models import EMBEEDING_MODEL_NAME

load_dotenv()


llm_model = ChatOpenAI(model="gpt-5-nano")
embedding_model = OpenAIEmbeddings(model=EMBEEDING_MODEL_NAME)

# llm_model = ChatOllama(model = "llama3.3:70b")
# llm_model = ChatOllama(model="alibayram/Qwen3-30B-A3B-Instruct-2507:latest")
# graph_llm_model = ChatOllama(model="llama3.3:70b")
graph_llm_model = ChatOpenAI(model="gpt-5-mini")
# embedding_model = OllamaEmbeddings(model="dengcao/Qwen3-Embedding-8B:Q5_K_M")
CHUNK_SIZE = 512
CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
