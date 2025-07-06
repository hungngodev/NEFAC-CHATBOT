import os
from typing import Dict, List, Optional, Union

import pinecone  # type: ignore
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore  # type: ignore

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")


# --- Pinecone Setup Helper ---
def _get_pinecone_index():
    pinecone_api_key = os.environ["PINECONE_API_KEY"]
    pinecone_env = os.environ["PINECONE_ENVIRONMENT"]
    index_name = os.environ["PINECONE_INDEX_NAME"]
    # Check for pinecone.init and pinecone.Index (v2.x)
    if not hasattr(pinecone, "init") or not hasattr(pinecone, "Index"):
        raise ImportError("Pinecone client does not have 'init' or 'Index'. Please install pinecone-client v2.x.")
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)  # type: ignore
    return pinecone.Index(index_name)  # type: ignore


# --- Upsert Session Memory ---
def add_memory_to_pinecone(session_id: str, memory_text: str, metadata: Optional[Dict[str, Union[str, int, float, bool]]] = None, namespace: str = "session-memory"):
    """Embed and upsert a memory item for the current session into Pinecone."""
    if PineconeVectorStore is None or pinecone is None:
        raise ImportError("Pinecone dependencies not installed.")
    index = _get_pinecone_index()
    embedding = embedding_model.embed_query(memory_text)
    meta: Dict[str, Union[str, int, float, bool]] = metadata if metadata is not None else {}
    meta["session_id"] = session_id
    index.upsert(vectors=[{"id": f"{session_id}_{hash(memory_text)}", "values": embedding, "metadata": meta}], namespace=namespace)


# --- Retrieve Session Memory ---
def retrieve_memory_from_pinecone(session_id: str, query: str, top_k: int = 5, namespace: str = "session-memory") -> List[Dict[str, Union[str, int, float, bool]]]:
    """Embed the query and retrieve top-k relevant session memory items from Pinecone."""
    if PineconeVectorStore is None or pinecone is None:
        raise ImportError("Pinecone dependencies not installed.")
    index = _get_pinecone_index()
    embedding = embedding_model.embed_query(query)
    results = index.query(vector=embedding, filter={"session_id": {"$eq": session_id}}, top_k=top_k, include_metadata=True, namespace=namespace)
    return [match["metadata"] for match in results["matches"]]


# --- Get Retriever for LangChain ---
def get_pinecone_session_memory_retriever(session_id: str, namespace: str = "session-memory"):
    """Return a Pinecone retriever for session-scoped memory (for use with LangChain)."""
    if PineconeVectorStore is None or pinecone is None:
        raise ImportError("Pinecone dependencies not installed.")
    index = _get_pinecone_index()
    vectorstore = PineconeVectorStore(
        index=index,
        embedding=embedding_model,
        namespace=namespace,
        filter={"session_id": {"$eq": session_id}},
    )
    return vectorstore.as_retriever()
