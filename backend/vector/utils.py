# general
from dotenv import load_dotenv
import logging

import faiss
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings 
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore

from document.loader import load_all_documents

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

# Initialize docstore -- MAKE PERMANENT FILE
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(1536), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
all_docs = []


def add_documents_to_store(_, info, documents):
  
    new_docs, new_vids = load_all_documents()

    logger.info("new_docs: ", new_docs)
    logger.info("new_vids: ", new_vids)

    chunked_docs = chunk_documents(new_docs)
    chunked_vids = chunk_documents(new_vids)
    all_doc_types = chunked_docs + chunked_vids
    vector_store.add_documents(documents = all_doc_types)

    return all_doc_types

def retrieve_documents(query):
    pass
def create_vectorstore_filter(roleFilter=None, contentType=None, resourceType=None):
    """
    Creates a metadata filter function for vector store retriever that checks if single target values
    exist in corresponding metadata arrays.
    
    Args:
        roleFilter (str, optional): Target audience value to match
        contentType (str, optional): Target nefac_category value to match
        resourceType (str, optional): Target resource_type value to match
        
    Returns:
        function: A filter function that can be used with vectorstore.as_retriever()
    """
    def filter_func(metadata):
        # Check audience/roleFilter
        if roleFilter is not None:
            if roleFilter not in metadata['audience']:
                return False
                
        # Check nefac_category/contentType
        if contentType is not None:
            if contentType not in metadata['nefac_category']:
                return False
                
        # Check resource_type/resourceType
        if resourceType is not None:
            if resourceType not in metadata['resource_type']:
                return False
                
        # If all specified filters pass, return True
        return True
    
    return filter_func

# Function to chunk documents
def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=25)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs