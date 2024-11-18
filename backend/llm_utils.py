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

# loaders
from langchain_community.document_loaders import PyPDFLoader, YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat



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
    new_vids = youtubeLoader()
    # set vids "start_seconds" to page number
    for vid in new_vids:
        vid.metadata['page'] = vid.metadata['start_seconds']
    chunked_docs = chunk_documents(new_docs)
    chunked_vids = chunk_documents(new_vids)

    all_doc_types = chunked_docs + chunked_vids
    vector_store.add_documents(documents = all_doc_types)
    return all_doc_types

# TODO: NEEDS IMPLEMENTATION
def load_documents_from_directory():
    # Load all new documents from the directory "docs/" of all types
    pass

def retrieve_documents(query):
    pass

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

        Answer the question provided by the user. USE THE MOST RELEVANT SOURCES FROM THE CONTEXT TO ANSWER THE QUESTION.
        
        Please follow the following rules:
        1. For each question, answer the question and provide a source.
        2. Exclude the sources that are irrelevant to the final answer.
        3. Include sources and page numbers in the answer.
        4. Do not use any external sources other than the ones provided.
        5. Do not provide any false information.
        6. Do not provide any information that is not supported by the sources.
        7. Do not provide any information that is not relevant to the question.
        8. Do not hallucinate or make up any information.
        Sources:
            {context}

        Question: {question}

        Helpful answer:
        """

    retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 20},
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

def youtubeLoader():

    loader = YoutubeLoader.from_youtube_url(
        "https://www.youtube.com/watch?v=0oMe5k7MPxs",
        add_video_info=False, # Set to True to include video metadata
        transcript_format=TranscriptFormat.CHUNKS,
        chunk_size_seconds=30,
    )
    print("youtubeLoader")
    print("\n\n".join(map(repr, loader.load())))
    return loader.load()
