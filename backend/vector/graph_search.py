"""
Graph RAG Retriever for Neo4j Knowledge Graph
Follows the retriever pattern from:
https://blog.langchain.com/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs/

- Extracts entities from a user question using an LLM
- Uses a full-text index in Neo4j to find relevant nodes
- Retrieves the neighborhood (direct relationships) for each entity
- Returns structured context for use in a RAG pipeline
"""

import os
from typing import List

from langchain.prompts import ChatPromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# --- Entity Extraction Schema ---
class Entities(BaseModel):
    """Identifying information about entities."""

    names: List[str] = Field(
        ...,
        description="All the person, organization, or business entities that appear in the text.",
    )


# --- LLM and Prompt for Entity Extraction ---
llm = ChatOpenAI(temperature=0, model="gpt-4-turbo")
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are extracting organization and person entities from the text.",
        ),
        (
            "human",
            "Use the given format to extract information from the following input: {question}",
        ),
    ]
)
entity_chain = prompt | llm.with_structured_output(Entities)

# --- Neo4j Graph Connection ---
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)


# --- Fulltext Index Helper ---
def generate_full_text_query(input: str) -> str:
    """
    Generate a full-text search query for a given input string.
    Allows for some misspellings using ~2 fuzziness.
    """

    def remove_lucene_chars(s):
        # Remove Lucene special characters
        import re

        return re.sub(r"[+\-!(){}\[\]^\"~*?:\\/]|&&|\|\|", "", s)

    words = [el for el in remove_lucene_chars(input).split() if el]
    if not words:
        return ""
    if len(words) == 1:
        return f"{words[0]}~2"
    return " AND ".join([f"{w}~2" for w in words])


# --- Graph Retriever ---
def structured_retriever(question: str, limit: int = 2) -> str:
    """
    For a given question, extract entities, find them in the graph using full-text index,
    and return their direct relationships (neighborhood) as context.
    """
    result = ""
    entities = entity_chain.invoke({"question": question})
    for entity in entities["names"]:
        fulltext_query = generate_full_text_query(entity)
        cypher = f"""
        CALL db.index.fulltext.queryNodes('entity', $query, {{limit:{limit}}})
        YIELD node,score
        CALL {{
          MATCH (node)-[r]->(neighbor)
          RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
          UNION
          MATCH (node)<-[r]-(neighbor)
          RETURN neighbor.id + ' - ' + type(r) + ' -> ' +  node.id AS output
        }}
        RETURN output LIMIT 50
        """
        response = graph.query(cypher, {"query": fulltext_query})
        result += "\n".join([el["output"] for el in response]) + "\n"
    return result.strip()


# --- Main Retriever Function ---
def graph_rag_retrieve(question: str) -> str:
    """
    Main entrypoint for retrieving graph-based context for a question.
    Returns a string with the structured neighborhood information.
    """
    return structured_retriever(question)


# Example usage:
# context = graph_rag_retrieve("Who is Elizabeth I?")
# print(context)
