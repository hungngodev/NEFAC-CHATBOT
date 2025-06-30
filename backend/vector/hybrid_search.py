import logging
import os

from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_openai import OpenAIEmbeddings

# Optional: Qdrant for vector DB retrieval
try:
    from langchain_qdrant import QdrantVectorStore  # type: ignore
    from qdrant_client import QdrantClient  # type: ignore
except ImportError:
    QdrantVectorStore = None
    QdrantClient = None
    print("Warning: langchain_qdrant or qdrant_client not installed. Qdrant vector DB retrieval will be skipped.")

from load_env import load_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")


def get_qdrant_retriever():
    """Return a Qdrant retriever for dense/semantic search."""
    if QdrantVectorStore is None or QdrantClient is None:
        raise ImportError("Qdrant dependencies not installed.")
    qdrant_url = os.environ["QDRANT_ENDPOINT"]
    collection_name = os.environ["QDRANT_CLUSTER_ID"]
    api_key = os.environ.get("QDRANT_API_KEY")
    client = QdrantClient(url=qdrant_url, api_key=api_key)
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model,
    )
    return vectorstore.as_retriever()


def get_bm25_retriever():
    """Return an ElasticSearchBM25Retriever for sparse/keyword search."""
    elasticsearch_url = os.environ["ES_HOST"]
    index_name = os.environ["ES_INDEX"]
    return ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)


def get_hybrid_retriever():
    """Return a hybrid retriever combining Qdrant and ElasticSearchBM25Retriever."""
    from langchain.retrievers.ensemble import EnsembleRetriever

    dense = get_qdrant_retriever()
    sparse = get_bm25_retriever()
    return EnsembleRetriever(retrievers=[dense, sparse], weights=[0.5, 0.5])


def get_cohere_rerank_retriever():
    """
    Return a retriever that performs hybrid retrieval (Qdrant + BM25) and reranks results with CohereRerank.
    Requires COHERE_API_KEY in the environment.
    Usage:
        retriever = get_cohere_rerank_retriever()
        docs = retriever.invoke("your query")
    """
    # Ensure Cohere API key is set
    if "COHERE_API_KEY" not in os.environ:
        raise EnvironmentError("COHERE_API_KEY must be set in the environment.")
    base_retriever = get_hybrid_retriever()
    compressor = CohereRerank(model="rerank-english-v3.0")
    compression_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)
    return compression_retriever
