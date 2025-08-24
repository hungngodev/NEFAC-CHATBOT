from dotenv import load_dotenv
from langchain_ollama import ChatOllama, OllamaEmbeddings

load_dotenv()


# llm_model = ChatOpenAI(model="gpt-5-nano")
# embedding_model = OpenAIEmbeddings(model=EMBEEDING_MODEL_NAME)

# llm_model = ChatOllama(model = "llama3.3:70b")
llm_model = ChatOllama(model="alibayram/Qwen3-30B-A3B-Instruct-2507:latest")
graph_llm_model = ChatOllama(model="llama3.3:70b")
embedding_model = OllamaEmbeddings(model="dengcao/Qwen3-Embedding-8B:Q5_K_M")
# Chunking configuration for all loaders
CHUNK_SIZE = 1024  # Number of characters per chunk (PDF, HTML)

CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"
