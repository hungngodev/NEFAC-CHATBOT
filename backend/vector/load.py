import logging
import os
import threading

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from load_env import load_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

FAISS_STORE_PATH = "faiss_store"

# Global variables for thread-safe vector store management
_vector_store = None
_vector_store_lock = threading.RLock()
_is_loading = False
_loading_progress = {"current": 0, "total": 0, "status": "initializing"}


class ThreadSafeVectorStore:
    """Wrapper for FAISS vector store to make it thread-safe"""

    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.lock = threading.RLock()

    def similarity_search(self, query, k=4, **kwargs):
        with self.lock:
            return self.vector_store.similarity_search(query, k=k, **kwargs)

    def as_retriever(self, **kwargs):
        # Create a thread-safe retriever wrapper
        class ThreadSafeRetriever:
            def __init__(self, wrapped_store):
                self.wrapped_store = wrapped_store

            def invoke(self, query):
                with self.wrapped_store.lock:
                    return self.wrapped_store.vector_store.as_retriever(**kwargs).invoke(query)

        return ThreadSafeRetriever(self)

    def save_local(self, path):
        with self.lock:
            self.vector_store.save_local(path)


def initialize_empty_vector_store():
    """Initialize an empty FAISS vector store"""
    logger.info("Initializing empty vector store...")

    if os.path.exists(FAISS_STORE_PATH):
        logger.info("Existing vector store found, loading...")
        vector_store = FAISS.load_local(
            FAISS_STORE_PATH,
            embeddings=embedding_model,
            allow_dangerous_deserialization=True,
        )
    else:
        logger.info("Creating new empty vector store...")
        vector_store = FAISS(
            embedding_function=embedding_model,
            index=faiss.IndexFlatIP(3072),  # text-embedding-3-large -> 3072 dimensions
            docstore=InMemoryDocstore({}),
            index_to_docstore_id={},
        )

    logger.info("Vector store initialized successfully")
    return ThreadSafeVectorStore(vector_store)


def get_vector_store():
    """Get the vector store, initializing if needed"""
    global _vector_store

    with _vector_store_lock:
        if _vector_store is None:
            _vector_store = initialize_empty_vector_store()

        return _vector_store.vector_store


def get_loading_status():
    """Get current loading status"""
    return _loading_progress.copy()


def is_loading():
    """Check if documents are currently being loaded"""
    return _is_loading


# Initialize the vector store immediately when module is imported
vector_store = get_vector_store()
