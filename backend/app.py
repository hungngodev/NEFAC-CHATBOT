import logging
import os
from typing import List

from ariadne import MutationType, QueryType, gql, make_executable_schema
from ariadne.asgi import GraphQL
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llm.main import ask_llm_stream
from pydantic import BaseModel
from vector.utils import retrieve_documents
from vector.load import add_all_documents_to_store
from load_env import load_env

load_env()

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GraphQL Type Definitions
type_defs = gql("""
                
    interface Document {
        page_content: String
    }

    type Citation {
        id: String!
        context: String!
    }
                
    type Query {
        retrieveDocuments(query: String!): [Document]
    }

    type Mutation {
        addDocuments(documents: [String!]!): String!
    }
""")

# Create Query and Mutation types
query = QueryType()
mutation = MutationType()
    
# Create the executable schema
schema = make_executable_schema(type_defs, query, mutation)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; change this to specific domains as needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods; you can restrict this to specific methods if desired
    allow_headers=["*"],  # Allows all headers; you can restrict this to specific headers if desired
)

@app.get("/a***REMOVED***llm")
async def ask_llm(
    query: str,
    convoHistory: str = "",
    roleFilter: str = None,
    contentType: str = None,
    resourceType: str = None,
):
    
    try:        
        # Return the stream as a response using StreamingResponse
        return StreamingResponse(
            ask_llm_stream(None, query, convoHistory, roleFilter, contentType, resourceType),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount the GraphQL ASGI application
app.add_route("/graphql", GraphQL(schema, debug=True))

@query.field("retrieveDocuments")
def resolve_retrieve_documents(_, info, query):
    try:
        return retrieve_documents(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@mutation.field("addDocuments")
async def resolve_add_documents(_, info, documents):
    try:
        add_all_documents_to_store(_, info, documents)
        print("Documents added!")
        return "Documents added!"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run using: uvicorn app:app --reload