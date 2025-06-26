from typing import List
from tqdm import tqdm
from langchain_ollama import OllamaLLM
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_community.embeddings import OllamaEmbeddings
import logging
import os
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

# Contextual retrieval prompt
contextual_prompt_template = ChatPromptTemplate.from_template(
    """<document>\n{{document}}\n</document>\nHere is the chunk we want to situate within the whole document\n<chunk>\n{{chunk}}\n</chunk>\nPlease provide a concise context that situates this chunk within the overall document, focusing on its relevance to First Amendment rights, government transparency, public records, legal advocacy, or journalism in New England. Answer only with the succinct context and nothing else."""
)

llm = OllamaLLM(model="llama3:70b-instruct")
logger = logging.getLogger(__name__)

# --- Ollama Embedding Model for Qwen3:8b ---
ollama_embedding_model = OllamaEmbeddings(model="qwen3:8b")


# --- Qdrant Upload Logic ---
def upload_to_qdrant(documents: List[Document], embedding_model):
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")
        client = QdrantClient(url=qdrant_url, api_key=api_key)
        vectorstore = QdrantVectorStore.from_documents(
            documents,
            embedding=embedding_model,
            client=client,
            collection_name=collection_name,
        )
        logger.info(
            f"✓ Uploaded {len(documents)} vectors to Qdrant collection '{collection_name}' at {qdrant_url, vectorstore}"
        )
    except Exception as e:
        logger.exception(f"Error uploading to Qdrant: {e}")


def contextualize_chunk(document: str, chunk: str) -> tuple[str, str]:
    prompt = contextual_prompt_template.format(document=document, chunk=chunk)
    try:
        context = llm.invoke(prompt).strip()
        contextualized_chunk = context + " " + chunk
        return context, contextualized_chunk
    except Exception as e:
        logger.exception(f"Contextualization failed: {e}")
        return "", chunk


def format_contextualized_chunk(context: str, chunk: str) -> str:
    return f"Context: {context}\nContent: {chunk}"


def _contextualize_chunk_dict(args: dict) -> dict:
    context, _ = contextualize_chunk(args["document"], args["chunk"])
    return {"context": context, "chunk": args["chunk"]}


def _format_contextualized_chunk_dict(args: dict) -> str:
    return format_contextualized_chunk(args["context"], args["chunk"])


contextualize_chunk_runnable = RunnableLambda(
    _contextualize_chunk_dict
) | RunnableLambda(_format_contextualized_chunk_dict)


def contextualize_documents_workflow(documents):
    contextualized_documents = []
    for doc in tqdm(documents, desc="Contextualizing chunks"):
        result = contextualize_chunk_runnable.invoke(
            {"document": doc.page_content, "chunk": doc.page_content}
        )
        doc.metadata["contextualization"] = result.split("\n")[0].replace(
            "Context: ", ""
        )
        doc.metadata["original_chunk"] = doc.page_content
        doc.page_content = result
        contextualized_documents.append(doc)
    return contextualized_documents


def save_contextual_elasticsearch_bm25_for_backend(
    contextualized_documents: List[Document],
):
    elasticsearch_url = "http://elasticsearch:9200"
    index_name = "nefac-contextual-index"
    retriever = ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)
    texts = [doc.page_content for doc in contextualized_documents]
    retriever.add_texts(texts)
    print(
        f"Contextualized documents uploaded to Elasticsearch index '{index_name}' at {elasticsearch_url}"
    )


# --- Contextualize and Index Function ---
def contextualize_and_index_documents(documents, embedding_model=None, test_mode=False):
    if embedding_model is None:
        embedding_model = ollama_embedding_model
    contextualized_documents = contextualize_documents_workflow(documents)
    if not test_mode:
        upload_to_qdrant(contextualized_documents, embedding_model)
        save_contextual_elasticsearch_bm25_for_backend(contextualized_documents)
    return contextualized_documents
