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
import glob
from langchain_core.prompts import PromptTemplate

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.chains import StuffDocumentsChain ,LLMChain

from langchain_community.document_loaders import PyPDFLoader


os.environ["OPENAI_API_KEY"] = ""
# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
# Initialize docstore -- MAKE PERMANENT FILE
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(1536), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
all_docs = []

# Add documents to the FAISS vector store
def add_documents_to_store(_, info, documents):

    # convert doc paths to Doc objects
    #new_docs = load_documents_from_directory()
    new_docs = pdfLoader()
    chunked_docs = chunk_documents(new_docs)
    vector_store.add_documents(documents = chunked_docs)
    return new_docs

# Delete documents from the FAISS vector store
# def delete_documents_from_store():

# TODO: NEEDS IMPLEMENTATION
def load_documents_from_directory():
    loader = DirectoryLoader("docs/")
    docs = loader.load()
    print(docs)
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

    # TODO: NEEDS REVISING?

    docs = vector_store.similarity_search(query=query, k=20)
    print(docs)
    #docs = [Document(page_content=doc.page_content) for doc in docs]
    docs = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs if doc.page_content is not None]
    
    return docs

# Function to chunk documents
def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunked_docs = text_splitter.split_documents(docs)
    return chunked_docs

# Function to ask the LLM
async def ask_llm(_, info, query):

    response = await custom_QA(_, info, query)
    
    return response['result']
    


async def custom_QA(_, info, query):

    prompt_template = """

        Your purpose it to act as a search engine. Given a search query, you need to retrieve the most relevant sources.
        
        Please follow the following rules:
        1. For each search query, you must provide the source itself as well as a quick description of the source.
        2. Exclude the sources that are irrelevant to the final answer.
        3. Format the response as follows:
            Source: "path to the source"
            Page: "page number"
            Description: "quick description of the source"
        4. Do not use any external sources other than the ones provided.
        Sources:
            {context}

        Search Query: {question}
        """

    retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 2},
    )
    QA_CHAIN_PROMPT = PromptTemplate.from_template(prompt_template) # prompt_template defined above
    llm_chain = LLMChain(llm=OpenAI(temperature = 0), prompt=QA_CHAIN_PROMPT, callbacks=None, verbose=True)
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source", "page"],
        template="Context:\ncontent:{page_content}\nsource:{source}\npage:{page}\n",
    )
    combine_documents_chain = StuffDocumentsChain(
        llm_chain=llm_chain,
        document_variable_name="context",
        document_prompt=document_prompt,
        callbacks=None,
    )
    qa = RetrievalQA(
        combine_documents_chain=combine_documents_chain,
        callbacks=None,
        verbose=True,
        retriever=retriever,
        return_source_documents = True,
    )
    response = qa(query)

    print(response)
    return response

def pdfLoader():
    # Load all PDF documents from the directory "docs/"
    all_docs_path = "docs/legal_docs/*"
    all_docs = glob.glob(all_docs_path)
    all_pages = []
    print(all_docs)
    for idx, doc in enumerate(all_docs):
        loader = PyPDFLoader(doc)
        pages = loader.load_and_split()
        all_pages.extend(pages)

    return all_pages

    

    