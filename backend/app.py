from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ariadne import QueryType, MutationType, make_executable_schema, gql
from ariadne.asgi import GraphQL
from pydantic import BaseModel
from typing import List

from llm_utils import add_documents_to_store, retrieve_documents, ask_llm

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; change this to specific domains as needed
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods; you can restrict this to specific methods if desired
    allow_headers=["*"],  # Allows all headers; you can restrict this to specific headers if desired
)



# GraphQL Type Definitions
type_defs = gql("""
                
    interface Document {
        page_content: String
    }

    type Citation {
        id: String!
        context: String!
    }

    type SearchResult {
        title: String!
        link: String!
        summary: String!
        citations: [Citation!]!
    }
            
    type Query {
        askLlm(prompt: String!, roleFilter: String): [SearchResult!]!
        retrieveDocuments(query: String!): [Document]
    }

    type Mutation {
        addDocuments(documents: [String!]!): String!
    }
""")


# Create Query and Mutation types
query = QueryType()
mutation = MutationType()

# Define the resolvers
@query.field("askLlm")
async def resolve_ask_llm(_, info, prompt, roleFilter=None):
    try:
        print("Role Filter: ", roleFilter)
        response = await ask_llm(_, info, prompt, roleFilter)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@query.field("retrieveDocuments")
def resolve_retrieve_documents(_, info, query):
    try:
        return retrieve_documents(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@mutation.field("addDocuments")
async def resolve_add_documents(_, info, documents):
    try:
        add_documents_to_store(_, info, documents)
        print("Documents added!")
        return "Documents added!"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create the executable schema
schema = make_executable_schema(type_defs, query, mutation)

# Mount the GraphQL ASGI application
app.add_route("/graphql", GraphQL(schema, debug=True))

# Run using: uvicorn app:app --reload