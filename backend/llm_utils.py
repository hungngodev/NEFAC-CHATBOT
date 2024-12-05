
# general
import os
import glob
import json
from dotenv import load_dotenv
import logging

# vector store + embeddings
import faiss
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings 
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.docstore.in_memory import InMemoryDocstore


# retrieval chains + llm
from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain.chains import StuffDocumentsChain ,LLMChain
from langchain_community.llms import OpenAI

# loaders
from langchain_community.document_loaders import PyPDFLoader, YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat

# extras - potentially not needed
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# config
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize embeddings and FAISS vector store
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
# Initialize docstore -- MAKE PERMANENT FILE
docstore = InMemoryDocstore({})
vector_store = FAISS(embedding_function=embedding_model, index = faiss.IndexFlatL2(1536), docstore = docstore, index_to_docstore_id={})  # 768 is the embedding dimension size
all_docs = []

# Add documents to the FAISS vector store
def add_documents_to_store(_, info, documents):

    new_docs, new_vids = load_all_documents()

    logger.info("new_docs: ", new_docs)
    logger.info("new_vids: ", new_vids)

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
    
    return response
    


async def custom_QA(_, info, query):

    prompt_template = """

        Answer the question provided by the user. USE THE MOST RELEVANT SOURCES FROM THE CONTEXT TO ANSWER THE QUESTION.
        
        Please follow the following rules:
        1. For each question, answer the question and provide the source.
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
    
    prompt_template = """
    
    Use the following context to answer the query.
    
    Sources:
    {context}
    Instructions:
    - Generate a list of unique relevant sources from the context.
    - Provide the actual titles and links of the sources.
    - Summarize each source content in a way that answers the query.
    - Do not include duplicate sources or sources that are not relevant to the query.
    - Format the output as JSON in the following structure:
    {{
        "results": [
            {{
                "title": "Title of the source content",
                "link": "source_link",
                "summary": " Details answering to the query with full context (who what when why where how)",
                "citations": [
                    {{"id": "1", "context": "relevant quote/text use in summary"}},
                ]
            }},
            ...
        ]
    }}
    Question: {question}
    """

    retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 20},
    )

    QA_CHAIN_PROMPT = PromptTemplate.from_template(prompt_template) # prompt_template defined above
    
    llm_chain = LLMChain(llm=OpenAI(temperature = 0), prompt=QA_CHAIN_PROMPT, callbacks=None, verbose=True)
    
    document_prompt = PromptTemplate(
        input_variables=["page_content", "source", "page", "nefac_category", "resource_type", "audience"], # How to setup optional variables?
        template="Context:\ncontent:{page_content}\nsource:{source}\npage:{page}\nnefac_category:{nefac_category}\nresource_type:{resource_type}\naudience:{audience}\n",
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

    try:
        response = parse_llm_response(query, response)
    except Exception as e:
        logger.error(f"Error parsing the LLM response: {e}")

    return response

def parse_llm_response(query, response):

    # Parse the LLM's JSON response
    try:
        result = json.loads(response['result'])
        logger.info(f"Parsed LLM response: {result}")
        return result
    except Exception as e:
        logger.error(f"Error parsing the LLM response: {e}")
        # Fallback logic
        formatted_response = {
            "results": []
        }
        unique_titles = set()
        for i, doc in enumerate(response.get('source_documents', [])):
            title = doc.metadata.get("title", f"Source {i+1}")
            if title in unique_titles:
                continue
            unique_titles.add(title)
            # Generate a summary relevant to the query
            llm = OpenAI(temperature=0)
            summary_prompt = f"Based on the following content, provide a concise summary that answers the query: '{query}'\n\nContent:\n{doc.page_content}"
            try:
                summary = llm(summary_prompt).strip()
            except Exception as summ_err:
                logger.error(f"Error generating summary: {summ_err}")
                summary = "Summary unavailable."
            formatted_response["results"].append({
                "title": title,
                "link": doc.metadata.get("source", "#"),
                "summary": summary,
                "citations": [
                    {
                        "id": str(i+1),
                        "context": doc.page_content
                    }
                ]
            })
        return formatted_response["results"]
    
def pdfLoader(path, existing_docs):
    # Load all PDF documents from the directory "docs/"
    all_docs_path = glob.glob(path+"/*")
    new_docs = []
    new_pages = []
    duplicate_docs = []
    for idx, doc in enumerate(all_docs_path):
        doc_title = doc.split("/")[-1]
        if doc_title in existing_docs:
            duplicate_docs.append(doc_title)
        elif doc.endswith(".pdf") and doc_title not in new_docs:
            new_docs.append(doc_title)
            loader = PyPDFLoader(doc)
            pages = loader.load_and_split()
            new_pages.extend(pages)

    return new_pages, new_docs, duplicate_docs

def youtubeLoader(path, existing_vids):
    # Load all YouTube videos from list of URLs

    if 'yt_urls.txt' not in os.listdir(path):
        return [], [], []

    with open(f"{path}/yt_urls.txt", "r") as f:
        URLs = f.readlines()

    new_vids = []
    new_vids_chunks = []
    duplicate_vids = []

    for idx, url in enumerate(URLs):
        url_title = url.split('=')[1]
        if url_title in existing_vids:
            duplicate_vids.append(url_title)
        elif url_title not in existing_vids and url_title not in new_vids:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False, # Set to True to include video metadata
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=30,
            )
            new_vids.append(url_title)
            new_vids_chunks.extend(loader.load())
            # print("\n\n".join(map(repr, loader.load())))

    return new_vids_chunks, new_vids, duplicate_vids

# TODO: implement for txt files, images, etc. save vector store to disk. add optional filter params for each category (audience, resource_type, nefac_category) retrieved from frontend

def load_all_documents():
    all_pdfs = []
    all_pdf_pages = []
    all_yt_vids = []
    all_yt_vid_chunks = []

    by_audience_path = "docs/by_audience/*"
    by_resource_type_path = "docs/by_resource/*"
    by_nefac_category_path = "docs/by_content/*"

    all_audience = glob.glob(by_audience_path)
    all_resources = glob.glob(by_resource_type_path)
    all_content_types = glob.glob(by_nefac_category_path)
    
    for idx, audience_folder in enumerate(all_audience):
        new_pages, new_docs, dup_docs = pdfLoader(audience_folder, all_pdfs)
        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(audience_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1]
            page.metadata["audience"] = audience_folder.split("/")[-1]
            if 'nefac_category' not in page.metadata:
                page.metadata['nefac_category'] = ""
            if 'resource_type' not in page.metadata:
                page.metadata['resource_type'] = ""
        
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["audience"] = audience_folder.split("/")[-1]
            vid.metadata["page"] = vid.metadata["start_seconds"]
            if 'nefac_category' not in vid.metadata:
                vid.metadata['nefac_category'] = ""
            if 'resource_type' not in vid.metadata:
                vid.metadata['resource_type'] = ""

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata or existing_page.metadata['audience'] == "":
                        existing_page.metadata["audience"] = audience_folder.split("/")[-1]
                    if 'nefac_category' not in existing_page.metadata:
                        existing_page.metadata['nefac_category'] = ""
                    if 'resource_type' not in existing_page.metadata:
                        existing_page.metadata['resource_type'] = ""
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata or existing_vid.metadata['audience'] == "":
                        existing_vid.metadata["audience"] = audience_folder.split("/")[-1]
                    if 'nefac_category' not in existing_vid.metadata:
                        existing_vid.metadata['nefac_category'] = ""
                    if 'resource_type' not in existing_vid.metadata:
                        existing_vid.metadata['resource_type'] = ""
            

    for idx, resource_folder in enumerate(all_resources):
        new_pages, new_docs, dup_docs = pdfLoader(resource_folder, all_pdfs)
        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(resource_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1]
            page.metadata["resource_type"] = resource_folder.split("/")[-1]

            if 'nefac_category' not in page.metadata:
                page.metadata['nefac_category'] = ""
            if 'audience' not in page.metadata:
                page.metadata['audience'] = ""

        # set vids "start_seconds" to page number
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["resource_type"] = resource_folder.split("/")[-1]
            vid.metadata["page"] = vid.metadata["start_seconds"]

            if 'nefac_category' not in vid.metadata:
                vid.metadata['nefac_category'] = ""
            if 'audience' not in vid.metadata:
                vid.metadata['audience'] = ""

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata:
                        existing_page.metadata["audience"] = ""
                    if 'nefac_category' not in existing_page.metadata:
                        existing_page.metadata['nefac_category'] = ""
                    if 'resource_type' not in existing_page.metadata or existing_page.metadata['resource_type'] == "":
                        existing_page.metadata['resource_type'] = resource_folder.split("/")[-1]
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata:
                        existing_vid.metadata["audience"] = ""
                    if 'nefac_category' not in existing_vid.metadata:
                        existing_vid.metadata['nefac_category'] = ""
                    if 'resource_type' not in existing_vid.metadata or existing_vid.metadata['resource_type'] == "":
                        existing_vid.metadata['resource_type'] = resource_folder.split("/")[-1]
            
    for idx, content_folder in enumerate(all_content_types):
        new_pages, new_docs, dup_docs = pdfLoader(content_folder, all_pdfs)

        all_pdfs.extend(new_docs)
        all_pdf_pages.extend(new_pages)

        new_yt_chunks, new_vids, dup_vids = youtubeLoader(content_folder, all_yt_vids)
        all_yt_vids.extend(new_vids)
        all_yt_vid_chunks.extend(new_yt_chunks)

        for page in new_pages:
            page.metadata['title'] = page.metadata['source'].split('/')[-1]
            page.metadata["nefac_category"] = content_folder.split("/")[-1]
            if 'resource_type' not in page.metadata:
                page.metadata['resource_type'] = ""
            if 'audience' not in page.metadata:
                page.metadata['audience'] = ""

        # set vids "start_seconds" to page number
        for vid in new_yt_chunks:
            vid.metadata["title"] = vid.metadata["source"].split('=')[1][:-2]
            vid.metadata["nefac_category"] = content_folder.split("/")[-1]
            vid.metadata["page"] = vid.metadata["start_seconds"]

            if 'resource_type' not in vid.metadata:
                vid.metadata['resource_type'] = ""
            if 'audience' not in vid.metadata:
                vid.metadata['audience'] = ""

        for dup_doc in dup_docs:
            for existing_page in all_pdf_pages:
                if existing_page.metadata["title"] == dup_doc:
                    if 'audience' not in existing_page.metadata:
                        existing_page.metadata["audience"] = ""
                    if 'nefac_category' not in existing_page.metadata or existing_page.metadata['nefac_category'] == "":
                        existing_page.metadata['nefac_category'] = content_folder.split("/")[-1]
                    if 'resource_type' not in existing_page.metadata:
                        existing_page.metadata['resource_type'] = ""
        
        for dup_vid in dup_vids:
            for existing_vid in all_yt_vid_chunks:
                if existing_vid.metadata["title"] == dup_vid:
                    if 'page' not in existing_vid.metadata or existing_vid.metadata['page'] == "":
                        existing_vid.metadata["page"] = existing_vid.metadata["start_seconds"]
                    if 'audience' not in existing_vid.metadata:
                        existing_vid.metadata["audience"] = ""
                    if 'nefac_category' not in existing_vid.metadata or existing_vid.metadata['nefac_category'] == "":
                        existing_vid.metadata['nefac_category'] = content_folder.split("/")[-1]
                    if 'resource_type' not in existing_vid.metadata:
                        existing_vid.metadata['resource_type'] = ""

    return all_pdf_pages, all_yt_vid_chunks

add_documents_to_store(" ", "info", " ")