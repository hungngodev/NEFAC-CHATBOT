from llm.chain import middleware_qa
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ask_llm_stream(_, query, convoHistory=""):
    """
    Stream responses from the new clean LLM implementation.
    Now uses the improved 5-query vector search approach.
    """
    logger.info(f"Query: {query}")
    async for chunk in middleware_qa(query, convoHistory):
        yield chunk