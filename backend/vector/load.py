import logging
import faiss
import os
import threading
import time
from document.loader import load_all_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from load_env import load_env
import pickle
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

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
    
    def add_documents(self, documents):
        with self.lock:
            if documents:
                logger.info(f"Adding {len(documents)} documents to vector store")
                self.vector_store.add_documents(documents)
                # Save after each addition to persist progress
                self.vector_store.save_local(FAISS_STORE_PATH)
                logger.info(f"Documents added and saved to {FAISS_STORE_PATH}")
    
    def save_local(self, path):
        with self.lock:
            self.vector_store.save_local(path)

def initialize_empty_vector_store():
    """Initialize an empty FAISS vector store"""
    logger.info("Initializing empty vector store...")
    
    if os.path.exists(FAISS_STORE_PATH):
        logger.info('Existing vector store found, loading...')
        vector_store = FAISS.load_local(
            FAISS_STORE_PATH,
            embeddings=embedding_model,
            allow_dangerous_deserialization=True
        )
    else:
        logger.info('Creating new empty vector store...')
        vector_store = FAISS(
            embedding_function=embedding_model, 
            index=faiss.IndexFlatIP(3072),  # text-embedding-3-large -> 3072 dimensions
            docstore=InMemoryDocstore({}), 
            index_to_docstore_id={}
        )
    
    logger.info("Vector store initialized successfully")
    return ThreadSafeVectorStore(vector_store)

def chunk_documents(docs):
    """Split documents into chunks"""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=32)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs

def process_single_document(doc_name, title_to_chunks, doc_type="unknown"):
    """Process a single document and return its chunks"""
    try:
        if doc_name not in title_to_chunks:
            logger.warning(f"Document {doc_name} not found in title_to_chunks")
            return []
        
        doc_chunks = title_to_chunks[doc_name]
        chunked_docs = chunk_documents(doc_chunks)
        
        logger.info(f"Processed {doc_name}: {len(doc_chunks)} original chunks -> {len(chunked_docs)} processed chunks")
        return chunked_docs
        
    except Exception as e:
        logger.error(f"Error processing document {doc_name}: {e}")
        return []

def add_documents_sequentially():
    """Add documents to vector store one by one in background"""
    global _is_loading, _loading_progress
    
    try:
        _is_loading = True
        logger.info("Starting sequential document addition...")
        
        # Load all documents and metadata
        all_documents, url_to_title, title_to_chunks, new_docs = load_all_documents()
        
        # Save metadata
        with open('doc_names.pkl', 'wb') as doc_names:
            pickle.dump(all_documents, doc_names)
        with open('url_to_title.pkl', 'wb') as u2t:
            pickle.dump(url_to_title, u2t)
        with open('title_to_chunks.pkl', 'wb') as t2c:
            pickle.dump(title_to_chunks, t2c)
        
        if not new_docs:
            logger.info("No new documents to add to vector store")
            _loading_progress["status"] = "complete"
            return
        
        new_docs_list = list(new_docs)
        _loading_progress["total"] = len(new_docs_list)
        _loading_progress["status"] = "adding_documents"
        
        logger.info(f"Found {len(new_docs_list)} new documents to add sequentially")
        
        # Process each document individually
        for i, doc_name in enumerate(new_docs_list, 1):
            try:
                _loading_progress["current"] = i
                logger.info(f"Processing document {i}/{len(new_docs_list)}: {doc_name}")
                
                # Determine document type
                doc_type = "pdf" if doc_name.endswith('.pdf') else "youtube"
                
                # Process single document
                chunked_docs = process_single_document(doc_name, title_to_chunks, doc_type)
                
                if chunked_docs:
                    # Add to vector store
                    with _vector_store_lock:
                        if _vector_store:
                            _vector_store.add_documents(chunked_docs)
                    
                    logger.info(f"Successfully added document {i}/{len(new_docs_list)}: {doc_name} ({len(chunked_docs)} chunks)")
                else:
                    logger.warning(f"No chunks generated for document: {doc_name}")
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing document {doc_name}: {e}")
                continue
        
        _loading_progress["status"] = "complete"
        logger.info(f"Sequential document addition complete. Processed {len(new_docs_list)} documents.")
        
    except Exception as e:
        logger.error(f"Error in sequential document addition: {e}")
        _loading_progress["status"] = "error"
    finally:
        _is_loading = False

def get_vector_store():
    """Get the vector store, initializing if needed"""
    global _vector_store
    
    with _vector_store_lock:
        if _vector_store is None:
            _vector_store = initialize_empty_vector_store()
            
            # Start background document loading
            logger.info("Starting background document loading...")
            thread = threading.Thread(target=add_documents_sequentially, daemon=True)
            thread.start()
        
        return _vector_store

def get_loading_status():
    """Get current loading status"""
    return _loading_progress.copy()

def is_loading():
    """Check if documents are currently being loaded"""
    return _is_loading

# Initialize the vector store immediately when module is imported
vector_store = get_vector_store()