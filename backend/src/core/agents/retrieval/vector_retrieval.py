import os
from typing import Any, List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

qdrant_url = os.environ["QDRANT_ENDPOINT"]
collection_name = os.environ["QDRANT_CLUSTER_ID"]
api_key = os.environ.get("QDRANT_API_KEY")

if api_key:
    client = QdrantClient(url=qdrant_url, api_key=api_key)
else:
    client = QdrantClient(url=qdrant_url)

embed_model = OpenAIEmbedding(model_name="text-embedding-3-small", api_key=os.getenv("OPENAI_EMBEDDING_API_KEY"), api_base=os.getenv("OPENAI_EMBEDDING_API_BASE"))

vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
index = VectorStoreIndex.from_vector_store(vector_store=vector_store, embed_model=embed_model)


class LlamaIndexRetrieverWrapper(BaseRetriever):
    index: Any
    similarity_top_k: int = 10

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        retriever = self.index.as_retriever(similarity_top_k=self.similarity_top_k)
        nodes = retriever.retrieve(query)
        documents = []
        for node in nodes:
            metadata = node.metadata.copy() if node.metadata else {}
            if node.score is not None:
                metadata["score"] = node.score
            # Use full content (including headers) as requested by user
            content = node.get_content()

            # Remove 'text' from metadata as it duplicates content and might be dirty
            metadata.pop("text", None)
            metadata.pop("_node_content", None)

            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
        return documents


vector_retriever = LlamaIndexRetrieverWrapper(index=index)
