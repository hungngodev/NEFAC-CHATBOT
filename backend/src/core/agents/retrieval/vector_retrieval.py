import os

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.config.models import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL_NAME

embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME)

qdrant_url = os.environ["QDRANT_ENDPOINT"]
collection_name = os.environ["QDRANT_CLUSTER_ID"]
api_key = os.environ.get("QDRANT_API_KEY")

if api_key:
    client = QdrantClient(url=qdrant_url, api_key=api_key)
else:
    client = QdrantClient(url=qdrant_url)

collections = client.get_collections()
collection_exists = any(col.name == collection_name for col in collections.collections)

if not collection_exists:
    print(f"Creating new collection: {collection_name}")
    client.create_collection(collection_name=collection_name, vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE))
    print(f"Collection {collection_name} created successfully")

vectorstore = QdrantVectorStore(
    client=client,
    collection_name=collection_name,
    embedding=embedding_model,
)
vector_retriever = vectorstore.as_retriever()


@tool(description="Performs semantic vector search using Qdrant.")
def vector_search(query: str, top_k: int = 10) -> list[Document]:
    local_retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
    documents = local_retriever.invoke(query)

    for doc in documents:
        if not hasattr(doc, "metadata") or doc.metadata is None:
            doc.metadata = {}
        doc.metadata["stream_tag"] = "vector_retrieved_docs"
        doc.metadata["retrieval_method"] = "vector_search"

    return documents
