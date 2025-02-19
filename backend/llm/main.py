from llm.chain import middleware_qa, custom_QA_structured
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ask_llm_stream(_, info, query, convoHistory="", roleFilter=None, contentType=None, resourceType=None):
    logger.info(f"Query: {query}")
    async for chunk in middleware_qa(_, info, query, convoHistory, roleFilter, contentType, resourceType):
        # Check if chunk is a dictionary (structured data)
        logger.info(f"Chunk: {chunk.content}")
        # if isinstance(chunk, dict):
        #     # Convert the dictionary to a JSON string
        #     chunk_data = json.dumps(chunk)
        #     yield f"data: {chunk_data}\n\n"
        # else:
        #     # If chunk is a string, just send it as is
        #     yield f"data: {chunk}\n\n"

    # If enough information is found, stream structured response
    if chunk == "1":
        async for chunk in custom_QA_structured(_, info, query, roleFilter, contentType, resourceType):
            # Check if chunk is a dictionary (structured data)

            # if isinstance(chunk, dict):
            #     chunk_data = json.dumps(chunk)
            #     yield f"data: {chunk_data}\n\n"
            # else:
            yield f"data: {chunk.content}\n\n"
    else:
        # If not enough information, stream follow-up question
        follow_up_chunk = {
            "title": "follow-up",
            "link": "",
            "summary": '',
            "citations": [{"id": "1", "context": "Follow-up question"}]
        }
        chunk_data = json.dumps(follow_up_chunk)
        yield f"data: {chunk_data}\n\n"

