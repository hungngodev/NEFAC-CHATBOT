from llm.chain import middleware_qa
import json
import logging
from vector.load import vector_store

# def inspect_vector_store(vector_store):
#     # Retrieve the documents from the vector store
#     documents = vector_store.docstore._dict  # Access the internal document store

#     # Print out the contents of the vector store
#     for doc_id, doc in documents.items():
#         print(f"Document ID: {doc_id}")

#         print(f"Document Content: {doc.page_content}")
#         print(f"Metadata: {doc.metadata}")
#         print("-" * 40)  # Separator for readability
#     if not documents:
#         print("there are no documents in the store")

# inspect_vector_store(vector_store)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ask_llm_stream(_, query, convoHistory="", roleFilter=None, contentType=None, resourceType=None):
    logger.info(f"Query: {query}")
    async for chunk in middleware_qa(query, convoHistory, roleFilter, contentType, resourceType):
            yield chunk