import logging
import os
from typing import Any, List

from langchain_core.documents import Document
from langchain_elasticsearch import BM25Strategy, ElasticsearchStore
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.config.models import EMBEEDING_DIMENSIONS

logger = logging.getLogger(__name__)


def upload_to_qdrant(documents: List[Document], embedding_model) -> Any:
    """Upload documents to Qdrant with systematic progress tracking."""
    if not documents:
        logger.warning("No documents to upload to Qdrant")
        return None

    try:
        qdrant_url = os.environ["QDRANT_ENDPOINT"]
        collection_name = os.environ["QDRANT_CLUSTER_ID"]
        api_key = os.environ.get("QDRANT_API_KEY")

        logger.info(f"Connecting to Qdrant at {qdrant_url}")

        # Initialize Qdrant client
        if api_key:
            client = QdrantClient(url=qdrant_url, api_key=api_key)
        else:
            client = QdrantClient(url=qdrant_url)

        # Check if collection exists, create if it doesn't
        try:
            logger.info(f"Checking Qdrant collection: {collection_name}")
            collections = client.get_collections()
            collection_exists = any(col.name == collection_name for col in collections.collections)

            if not collection_exists:
                logger.info(f"Creating new Qdrant collection: {collection_name}")
                client.create_collection(collection_name=collection_name, vectors_config=VectorParams(size=EMBEEDING_DIMENSIONS, distance=Distance.COSINE))
                logger.info(f"Collection {collection_name} created successfully")
            else:
                logger.info(f"Collection {collection_name} already exists")

        except Exception as e:
            logger.error(f"Error checking/creating collection: {e}")
            raise

        # Upload documents to Qdrant
        logger.info(f"Uploading {len(documents)} vectors to Qdrant...")

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

        logger.info(f"Successfully uploaded {len(documents)} vectors to Qdrant collection '{collection_name}'")
        return vectorstore

    except Exception as e:
        logger.error(f"Error uploading to Qdrant: {e}")
        raise


def save_contextual_elasticsearch_bm25_for_backend(contextualized_documents: List[Document]):
    """Save documents to Elasticsearch with systematic progress tracking."""
    if not contextualized_documents:
        logger.warning("No documents to upload to Elasticsearch")
        return

    elasticsearch_url = os.environ["ES_HOST"]
    index_name = os.environ["ES_INDEX"]

    logger.info(f"Connecting to Elasticsearch at {elasticsearch_url}")
    logger.info(f"Target index: {index_name}")

    try:
        store = ElasticsearchStore(
            index_name=index_name,
            es_url=elasticsearch_url,
            query_field="content",
            strategy=BM25Strategy(),
        )

        documents_with_metadata: list[Document] = []
        ids: list[str] = []
        for idx, doc in enumerate(contextualized_documents):
            metadata = dict(getattr(doc, "metadata", {}) or {})
            base_id = str(metadata.get("id") or metadata.get("filename") or "chunk")
            chunk_index = metadata.get("chunk_index")
            if chunk_index is None:
                chunk_index = idx
                metadata["chunk_index"] = chunk_index
            stable_id = f"{base_id}:{chunk_index}"
            documents_with_metadata.append(Document(page_content=doc.page_content, metadata=metadata))
            ids.append(stable_id)

        if documents_with_metadata:
            store.add_documents(documents_with_metadata, ids=ids)
        logger.info(f"Successfully indexed {len(contextualized_documents)} documents into Elasticsearch index '{index_name}' using BM25Strategy")

    except Exception as e:
        logger.error(f"Error uploading to Elasticsearch: {e}")
        raise


def contextualize_and_index_documents(documents, embedding_model=None, test_mode=False) -> Any:
    """
    Index documents into Qdrant and Elasticsearch with systematic progress tracking.
    Assumes input documents are already contextualized (context + chunk).
    """
    if not documents:
        logger.warning("No documents provided for contextual indexing")
        return []

    if embedding_model is None:
        from src.service.ingestion_service.settings import embedding_model as default_embedding_model

        embedding_model = default_embedding_model

    logger.info(f"Starting contextual indexing for {len(documents)} documents")

    if not test_mode:
        try:
            # Upload to Qdrant
            logger.info("Uploading to Qdrant vector database")
            upload_to_qdrant(documents, embedding_model)

            # Upload to Elasticsearch
            logger.info("Uploading to Elasticsearch BM25 index")
            save_contextual_elasticsearch_bm25_for_backend(documents)

            logger.info(f"Contextual indexing complete for {len(documents)} documents")

        except Exception as e:
            logger.error(f"Contextual indexing failed: {e}")
            raise
    else:
        logger.info("Test mode: Skipping actual database uploads")

    return documents
