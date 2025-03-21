from llm.chain import middleware_qa
import json
import logging
from vector.load import vector_store
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ask_llm_stream(_, query, convoHistory="", roleFilter="", contentType="", resourceType=""):
    logger.info(f"Query: {query}")
    async for chunk in middleware_qa(query, convoHistory, roleFilter, contentType, resourceType):
        yield chunk

def inspect_vector_store(vector_store, prompt='', k=5):
    """
    Inspect the contents of a FAISS vector store and print the results.
    
    Args:
        vector_store: The FAISS vector store instance.
        prompt (str): The query prompt to search for (default: '').
        k (int): Number of results to return when a prompt is provided (default: 5).
    """
    
    if prompt == '':
        # Retrieve all documents from the docstore
        documents = vector_store.docstore._dict
        if not documents:
            print("There are no documents in the store")
        else:
            print("Inspecting all documents in the vector store:")
            print("=" * 50)
            for doc_id, doc in documents.items():
                print(f"Document ID: {doc_id}")
                print(f"Document Content: {doc.page_content}")
                print(f"Metadata: {doc.metadata}")
                print("-" * 40)
    else:
        # Embed the prompt into a vector
        query_embedding = vector_store.embedding_function.embed_query(prompt)
        # Perform similarity search using FAISS index
        distances, indices = vector_store.index.search(np.array([query_embedding], dtype=np.float32), k)
        if len(indices[0]) == 0 or all(idx == -1 for idx in indices[0]):
            print(f"No matching documents found for prompt: '{prompt}'")
        else:
            print(f"Search results for prompt: '{prompt}'")
            print("=" * 50)
            for i in range(len(indices[0])):
                idx = indices[0][i]
                if idx in vector_store.index_to_docstore_id:
                    doc_id = vector_store.index_to_docstore_id[idx]
                    doc = vector_store.docstore.search(doc_id)
                    distance = distances[0][i]
                    print(f"Document ID: {doc_id}")
                    print(f"Document Content: {doc.page_content}")
                    print(f"Metadata: {doc.metadata}")
                    print(f"Similarity Score: {distance}")
                    print("-" * 40)

# inspect_vector_store(vector_store,'data cleaning 101')