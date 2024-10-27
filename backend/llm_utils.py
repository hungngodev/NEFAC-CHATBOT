import faiss
from langchain.embeddings import OpenAIEmbeddings  # Replace with Bedrock embeddings if using AWS Bedrock
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI  # Replace with Claude integration
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader
from langchain.docstore.in_memory import InMemoryDocstore
from langchain.retrievers.multi_query import MultiQueryRetriever
import os
os.environ["OPENAI_API_KEY"] = ""
# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
# Initialize docstore
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(768), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
all_docs = []
# Add documents to the FAISS vector store
def add_documents_to_store(_, info, documents):
    # convert doc paths to Doc objects
    new_docs = load_documents_from_directory()
    chunked_docs = chunk_documents(new_docs)
    vector_store.add_documents(documents = chunked_docs)
    return new_docs

# Delete documents from the FAISS vector store
# def delete_documents_from_store():

def load_documents_from_directory():
    loader = DirectoryLoader("./docs/test.txt")
    docs = loader.load()
    new_docs = []
    for doc in docs:
        if doc not in all_docs:
            new_docs.append(doc)
            all_docs.append(doc)
    print(f"Loaded {len(new_docs)} new documents")
    print(f"Total documents: {len(all_docs)}")
    return new_docs

# Retrieve documents from the FAISS vector store
def retrieve_documents(query):
    return vector_store.similarity_search(query=query, k=1)

# Function to chunk documents
def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs

# Function to ask the LLM
async def ask_llm(_, info, prompt):
    llm = OpenAI()
    response = llm.invoke(prompt)
    print(response)
    return response
    
