import logging
import os
from typing import Any, List

from elasticsearch import Elasticsearch
from langchain_community.retrievers import ElasticSearchBM25Retriever
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from tqdm import tqdm

from src.config.models import EMBEEDING_DIMENSIONS

logger = logging.getLogger(__name__)


# --- Qdrant Upload Logic ---
def upload_to_qdrant(documents: List[Document], embedding_model) -> Any:
    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")  # Will be None for local

        # Initialize Qdrant client to check/create collection
        with tqdm(total=1, desc="Connecting to Qdrant", leave=False) as pbar:
            if api_key:
                client = QdrantClient(url=qdrant_url, api_key=api_key)
            else:
                # Local Qdrant doesn't need API key
                client = QdrantClient(url=qdrant_url)
            pbar.update(1)

        # Check if collection exists, create if it doesn't
        try:
            with tqdm(total=1, desc="Checking Qdrant collection", leave=False) as pbar:
                collections = client.get_collections()
                collection_exists = any(col.name == collection_name for col in collections.collections)
                pbar.update(1)

            if not collection_exists:
                with tqdm(total=1, desc="Creating Qdrant collection", leave=False) as pbar:
                    print(f"Creating new collection: {collection_name}")
                    client.create_collection(collection_name=collection_name, vectors_config=VectorParams(size=EMBEEDING_DIMENSIONS, distance=Distance.COSINE))  # text-embedding-3-small dimension
                    print(f"Collection {collection_name} created successfully")
                    pbar.update(1)
        except Exception as e:
            print(f"Error checking/creating collection: {e}")

        # Use from_documents with connection parameters instead of passing client
        with tqdm(total=1, desc="Uploading to Qdrant", leave=False) as pbar:
            if api_key:
                vectorstore = QdrantVectorStore.from_documents(
                    documents,
                    embedding=embedding_model,
                    url=qdrant_url,
                    api_key=api_key,
                    collection_name=collection_name,
                )
            else:
                vectorstore = QdrantVectorStore.from_documents(
                    documents,
                    embedding=embedding_model,
                    url=qdrant_url,
                    collection_name=collection_name,
                )
            pbar.update(1)

        logger.info(f"✓ Uploaded {len(documents)} vectors to Qdrant collection '{collection_name}' at {qdrant_url}")
        return vectorstore
    except Exception as e:
        logger.exception(f"Error uploading to Qdrant: {e}")
        raise


def save_contextual_elasticsearch_bm25_for_backend(
    contextualized_documents: List[Document],
):
    elasticsearch_url = os.environ["ES_HOST"]
    index_name = os.environ["ES_INDEX"]
    print("ES_HOST =", os.environ.get("ES_HOST"))
    print("ES_INDEX =", os.environ.get("ES_INDEX"))

    # Initialize Elasticsearch client
    with tqdm(total=1, desc="Connecting to Elasticsearch", leave=False) as pbar:
        es = Elasticsearch(elasticsearch_url)
        pbar.update(1)

    with tqdm(total=1, desc="Setting up Elasticsearch index", leave=False) as pbar:
        if not es.indices.exists(index=index_name):
            # Create index and retriever if index doesn't exist
            keyword_retriever = ElasticSearchBM25Retriever.create(elasticsearch_url, index_name)
        else:
            # Just instantiate the retriever if index already exists
            keyword_retriever = ElasticSearchBM25Retriever(client=es, index_name=index_name)
        pbar.update(1)

    with tqdm(total=1, desc="Uploading to Elasticsearch", leave=False) as pbar:
        texts = [doc.page_content for doc in contextualized_documents]
        keyword_retriever.add_texts(texts)
        pbar.update(1)

    print(f"Contextualized documents uploaded to Elasticsearch index '{index_name}' at {elasticsearch_url}")


# --- Contextualize and Index Function ---
def contextualize_and_index_documents(documents, embedding_model=None, test_mode=False) -> Any:
    """
    Indexes already-contextualized documents into Qdrant and Elasticsearch.
    Assumes input documents are already contextualized (context + chunk).
    """
    if embedding_model is None:
        embedding_model = embedding_model

    with tqdm(total=2, desc="Indexing documents", colour="green") as pbar:
        if not test_mode:
            pbar.set_description("Uploading to Qdrant")
            upload_to_qdrant(documents, embedding_model)
            pbar.update(1)

            pbar.set_description("Uploading to Elasticsearch")
            save_contextual_elasticsearch_bm25_for_backend(documents)
            pbar.update(1)
        else:
            pbar.update(2)

    return documents
