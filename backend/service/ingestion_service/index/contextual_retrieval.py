import logging
import os
from typing import List

from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

llm = OllamaLLM(model="llama3.3:70b")
logger = logging.getLogger(__name__)

# --- Ollama Embedding Model for Qwen3:8b ---
ollama_embedding_model = OllamaEmbeddings(model="qwen3:8b")


# --- Qdrant Upload Logic ---
def upload_to_qdrant(documents: List[Document], embedding_model):
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")
        client = QdrantClient(url=qdrant_url, api_key=api_key)
        vectorstore = QdrantVectorStore.from_documents(
            documents,
            embedding=embedding_model,
            client=client,
            collection_name=collection_name,
        )
        logger.info(f"✓ Uploaded {len(documents)} vectors to Qdrant collection '{collection_name}' at {qdrant_url, vectorstore}")
    except Exception as e:
        logger.exception(f"Error uploading to Qdrant: {e}")


def save_contextual_elasticsearch_bm25_for_backend(
    contextualized_documents: List[Document],
):
    elasticsearch_url = "http://elasticsearch:9200"
    index_name = "nefac-contextual-index"
    retriever = ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)
    texts = [doc.page_content for doc in contextualized_documents]
    retriever.add_texts(texts)
    print(f"Contextualized documents uploaded to Elasticsearch index '{index_name}' at {elasticsearch_url}")


# --- Contextualize and Index Function ---
def contextualize_and_index_documents(documents, embedding_model=None, test_mode=False):
    """
    Indexes already-contextualized documents into Qdrant and Elasticsearch.
    Assumes input documents are already contextualized (context + chunk).
    """
    if embedding_model is None:
        embedding_model = ollama_embedding_model
    if not test_mode:
        upload_to_qdrant(documents, embedding_model)
        save_contextual_elasticsearch_bm25_for_backend(documents)
    return documents
