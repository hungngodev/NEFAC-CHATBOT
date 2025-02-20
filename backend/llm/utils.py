
# general
import os

import json
from dotenv import load_dotenv
import logging
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.llms import OpenAI
# validation
from validation import SearchResponse
from pydantic import BaseModel, ValidationError

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_docs(docs):
    return "\n\n".join(f"content:{doc.page_content}\nsource:{doc.metadata['source']}\npage:{doc.metadata['page']}\ntitle:{doc.metadata['title']}\nnefac_category:{doc.metadata['nefac_category']}\nresource_type:{doc.metadata['resource_type']}\naudience:{doc.metadata['audience']}\n" for doc in docs)
