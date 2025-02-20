from llm.chain import middleware_qa
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ask_llm_stream(_, query, convoHistory="", roleFilter=None, contentType=None, resourceType=None):
    logger.info(f"Query: {query}")
    async for chunk in middleware_qa(query, convoHistory, roleFilter, contentType, resourceType):
            yield chunk

