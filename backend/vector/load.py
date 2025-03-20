# general
import logging
import faiss
import os
from document.loader import load_all_documents
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from load_env import load_env
import pickle
# we need to make it so that when we add new documents, it adds them to the store.

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_env()

# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

FAISS_STORE_PATH = "faiss_store"

# adds all docs and videos to the vector store
def add_all_documents_to_store(vector_store):

    new_pages, new_vid_chunks, all_pdfs, all_yt_vids = load_all_documents()

    # Save all_pdfs so we don't add new stuff to the store thats already there in future
    with open('all_pdfs.pkl', 'wb') as pdf_file:
        pickle.dump(all_pdfs, pdf_file)
    print(all_pdfs)

    # Save all_yt_vids so we don't add new stuff to the store thats already there in future
    with open('all_yt_vids.pkl', 'wb') as yt_file:
        pickle.dump(all_yt_vids, yt_file)
    print(all_yt_vids)

    def chunk_documents(docs):
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=32)
        chunked_docs = text_splitter.split_documents(docs)
        return chunked_docs
    chunked_docs = chunk_documents(new_pages) if len(new_pages)>0 else []
    chunked_vids = chunk_documents(new_vid_chunks) if len(new_vid_chunks)>0 else []
    all_type_docs = chunked_docs + chunked_vids
    if len(all_type_docs)>0:
        vector_store.add_documents(documents = all_type_docs)
    vector_store.save_local(FAISS_STORE_PATH)

    return all_type_docs

def get_vector_store():
    if os.path.exists(FAISS_STORE_PATH):
        print('Store found and initialized')
        vector_store = FAISS.load_local(
            FAISS_STORE_PATH,
            embeddings=embedding_model,
            allow_dangerous_deserialization=True
        )
    else:
        print('Store not found')
        vector_store = FAISS(embedding_function=embedding_model, 
                        index = faiss.IndexFlatIP(3072), 
                        docstore = InMemoryDocstore({}), index_to_docstore_id={}) 
        add_all_documents_to_store(vector_store)
    return vector_store

vector_store = get_vector_store()
# vector_store.save_local(FAISS_STORE_PATH)
# add_documents_to_store(vector_store)

# docstore = InMemoryDocstore({})
# vector_store = FAISS(embedding_function=embedding_model, 
#                      index = faiss.IndexFlatIP(3072), 
#                      docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size





# all_docs = []
# add_documents_to_store()
# vector_store.save_local("faiss_store")
# vector_store.load_local("faiss_store",  embeddings=embedding_model, allow_dangerous_deserialization=True)
# retriever = vector_store.as_retriever(
#             search_type="similarity",
#             search_kwargs={"k": 10, "lambda_mult": 0.25, "score_threshold": 0.75},
#         ).with_config(tags=["retriever"])
# docs = retriever.invoke("NEFAC resources related to the First Amendment")
# print("Docs: ", docs)