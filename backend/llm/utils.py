
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

def fix_malformed_json(malformed_json):
    llm = OpenAI(temperature=0, max_tokens=2000)
    fix_prompt = """Fix this malformed JSON to match:
        {
            "results": [
                {
                    "title": "string",
                    "link": "string", 
                    "summary": "string",
                    "citations": [{"id": "string", "context": "string"}]
                }
            ]
        }

        Malformed JSON:
        %s

        Instructions:
            - Return only valid JSON.
            - Do not make up any information.
            - Do not hallucinate any information.
            - Do not include any information that is not in the original JSON.
            - Do not include any information that is not relevant to the JSON structure.
            - Do not include any information that is not supported by the JSON structure.
            - Do not include duplicate resources.
            - Sources should be unique.
            - Source links must match the original source links.
            - Titles can be slightly modified for readability, but must be concise.
            - The summary should be a short paragraph.
            - The citations should be relevant quotes from the source.

        Output:
        """ % malformed_json
    fixed_json = llm(fix_prompt).strip()
    print("fixed mal json: ", fixed_json)
    try:
        result = json.loads(fixed_json)
        validated_response = SearchResponse(**result)
        return validated_response.results
    except Exception as e:
        logger.error(f"Could not fix JSON: {e}")
        # Return a valid empty response
        return [{"title": "Error", "link": "", "summary": "No results found", "citations": []}]
    
def parse_llm_response(query, response):
    # Clean up the response
    json_response = response['result'].strip()
    print("parsing json_response: ", json_response)
    try:
        # Find the last complete JSON structure
        last_brace = json_response.rfind('}')
        if last_brace != -1:
            json_response = json_response[:last_brace + 1]
        
        # Try to parse as JSON
        result = json.loads(json_response)
        validated_response = SearchResponse(**result)
        return validated_response.results
        
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Error parsing LLM response: {e}")
        fixed_json = fix_malformed_json(json_response)
        return fixed_json
def format_docs(docs):
    return "\n\n".join(f"content:{doc.page_content}\nsource:{doc.metadata['source']}\npage:{doc.metadata['page']}\ntitle:{doc.metadata['title']}\nnefac_category:{doc.metadata['nefac_category']}\nresource_type:{doc.metadata['resource_type']}\naudience:{doc.metadata['audience']}\n" for doc in docs)
