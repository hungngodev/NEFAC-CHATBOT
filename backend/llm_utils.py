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

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

os.environ["OPENAI_API_KEY"] = "***REMOVED***proj-feC-Sb7M_q5Nb2SfVLKKoAoIIfEU44xgJsv2NEWQe8-6GY9qvWXZ_iyAxFjv84IQn8OdQQqCVrT3BlbkFJMWobBnRpaNjmX76ApxdRLbYPdgi-cJq314_ySz1-3Kqyf_qWF49jKD0ZKmxlmtds_LUDuS6z4A"
# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
# Initialize docstore -- MAKE PERMANENT FILE
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(1536), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
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
    loader = DirectoryLoader("docs/")
    docs = loader.load()
    new_docs = []
    for doc in docs:
        if doc not in all_docs:
            print(f"Adding document: {doc}")
            new_docs.append(doc)
            all_docs.append(doc)
    print(f"Loaded {len(new_docs)} new documents")
    print(f"Total documents: {len(all_docs)}")
    return new_docs

# Retrieve documents from the FAISS vector store
def retrieve_documents(query):
    return vector_store.similarity_search(query=query, k=20)

# Function to chunk documents
def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs

# Function to ask the LLM
async def ask_llm(_, info, query):
    llm = OpenAI()
    retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 1},
)
    message = """
        Answer this question using the provided context only.

        {question}

        Context:
        {context}
    """

    prompt = ChatPromptTemplate.from_messages([("human", message)])

    # rag_chain = {"context": retriever, "question": RunnablePassthrough()} | prompt | llm

    # response = rag_chain.invoke(query)

    # print(response) 

    docs = retrieve_documents(query)
    
    print(docs)

    return docs
    #return response
    