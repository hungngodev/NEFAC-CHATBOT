# general
import logging
import faiss
from document.loader import load_all_documents
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from load_env import load_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()
# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

# Initialize docstore -- MAKE PERMANENT FILE
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(1536), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
all_docs = []


def add_documents_to_store():
  
    new_docs, new_vids = load_all_documents()

    # logger.info("new_docs: ", new_docs)
    # logger.info("new_vids: ", new_vids)

    chunked_docs = chunk_documents(new_docs)
    chunked_vids = chunk_documents(new_vids)
    all_doc_types = chunked_docs + chunked_vids
    vector_store.add_documents(documents = all_doc_types)

    return all_doc_types
# Function to chunk documents
def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=25)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs

# add_documents_to_store()
# vector_store.save_local("faiss_store")
# vector_store.load_local("faiss_store",  embeddings=embedding_model, allow_dangerous_deserialization=True)
# retriever = vector_store.as_retriever(
#             search_type="similarity",
#             search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
#         ).with_config(tags=["retriever"])
# docs = retriever.invoke("NEFAC resources related to the First Amendment")
# print("Docs: ", docs)