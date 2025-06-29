import logging
import os
from typing import Any, Dict, List, Optional

from langchain.chains import GraphCypherQAChain
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_neo4j import Neo4jGraph  # Modern import
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Neo4j Graph Connection ---
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)

# --- LLM Setup ---
llm = ChatOpenAI(temperature=0, model="gpt-4-turbo")


# --- Entity Extraction Schema ---
class Entities(BaseModel):
    names: List[str] = Field(..., description="Canonical entity names (person, org, etc.) in the text.")
    types: Optional[List[str]] = Field(None, description="Entity types (Person, Organization, etc.)")


# --- Entity Extraction Chain ---
entity_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Extract canonical entities (with type if possible) from the text. Return as JSON."),
        ("human", "Input: {question}"),
    ]
)
entity_chain = entity_prompt | llm.with_structured_output(Entities)


def canonicalize_entities(entities: Entities) -> List[Dict[str, str]]:
    # Optionally add disambiguation logic here
    # For now, just pair names/types
    if entities.types and len(entities.names) == len(entities.types):
        return [{"name": n, "type": t} for n, t in zip(entities.names, entities.types)]
    return [{"name": n, "type": "Unknown"} for n in entities.names]


# --- Disambiguation Stub ---
def disambiguate_entities(entities: List[Dict[str, str]], context: str = "") -> List[Dict[str, str]]:
    # TODO: Use LLM or rules to disambiguate entities if needed
    return entities


# --- Graph Schema Fetching ---
def get_graph_schema() -> str:
    # Fetch and cache schema for LLM context
    try:
        schema = graph.get_schema  # property, not method
        return str(schema)
    except Exception as e:
        logger.warning(f"Could not fetch schema: {e}")
        return ""


# --- Fulltext Index Helper ---
def ensure_fulltext_index():
    # Ensure a fulltext index exists on __Entity__ label and name/id
    try:
        cypher = """
        CREATE FULLTEXT INDEX entity IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.name, e.id]
        """
        graph.query(cypher)
    except Exception as e:
        logger.warning(f"Could not create fulltext index: {e}")


def generate_full_text_query(input: str) -> str:
    import re

    def remove_lucene_chars(s):
        return re.sub(r"[+\-!(){}\[\]^\"~*?:\\/]|&&|\|\|", "", s)

    words = [el for el in remove_lucene_chars(input).split() if el]
    if not words:
        return ""
    if len(words) == 1:
        return f"{words[0]}~2"
    return " AND ".join([f"{w}~2" for w in words])


# --- Cypher Generation Chain (for fallback/manual use) ---
cypher_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a Neo4j Cypher expert. Given a question, entities, and the graph schema, generate an efficient Cypher query to answer the question. Use multi-hop, aggregation, or path queries if needed. Only return the Cypher statement.
Schema:
{schema}
""",
        ),
        ("human", "Question: {question}\nEntities: {entities}"),
    ]
)


def generate_cypher(question: str, entities: List[Dict[str, str]], schema: str) -> str:
    cypher_chain = cypher_prompt | llm
    cypher_result = cypher_chain.invoke({"question": question, "entities": entities, "schema": schema})
    # cypher_result may be a BaseMessage, a string, or a list
    if hasattr(cypher_result, "content"):
        content = cypher_result.content
        if isinstance(content, list):
            return "\n".join(str(x) for x in content).strip()
        return str(content).strip()
    if isinstance(cypher_result, list):
        return "\n".join(str(x) for x in cypher_result).strip()
    return str(cypher_result).strip()


# --- Path/Subgraph Extraction (manual fallback) ---
def extract_paths_between_entities(entities: List[Dict[str, str]], max_hops: int = 3) -> str:
    # Example: Find shortest paths between all pairs
    cyphers = []
    for i, e1 in enumerate(entities):
        for j, e2 in enumerate(entities):
            if i < j:
                cyphers.append(f"MATCH path = shortestPath((a:__Entity__ {{name: '{e1['name']}'}})-[*..{max_hops}]-(b:__Entity__ {{name: '{e2['name']}'}})) RETURN path LIMIT 3")
    return "\n".join(cyphers)


# --- Result Formatting ---
def format_results_as_documents(results: Any) -> List[Document]:
    # Convert Neo4j results to LangChain Documents with metadata
    docs = []
    if isinstance(results, list):
        for row in results:
            content = str(row)
            meta = {}
            if isinstance(row, dict):
                # Try to extract human-readable properties and source info
                meta = {k: v for k, v in row.items() if k != "text" and k != "content"}
                content = row.get("text") or row.get("content") or str(row)
            docs.append(Document(page_content=content, metadata=meta))
    else:
        docs.append(Document(page_content=str(results), metadata={}))
    return docs


# --- Main Graph RAG Retriever ---
def graph_rag_retrieve(question: str, use_llm_cypher: bool = True) -> List[Document]:
    """
    Advanced graph retriever: LLM-powered Cypher, entity canonicalization, path/subgraph, fallback to 1-hop.
    Returns a list of Document objects with human-readable content and source metadata for UI and answer citation.
    """
    ensure_fulltext_index()
    entities_raw = entity_chain.invoke({"question": question})
    # Ensure entities_raw is a Pydantic Entities model
    if isinstance(entities_raw, dict):
        entities_obj = Entities(**entities_raw)
    elif isinstance(entities_raw, Entities):
        entities_obj = entities_raw
    else:
        raise ValueError("Entity extraction returned unexpected type")
    entities = canonicalize_entities(entities_obj)
    entities = disambiguate_entities(entities, question)
    schema = get_graph_schema()

    # --- Modern: Use GraphCypherQAChain for LLM-driven Cypher and answer ---
    try:
        graph_qa_chain = GraphCypherQAChain.from_llm(llm, graph=graph)
        # This returns a string answer, but we want structured results for RAG
        answer = graph_qa_chain.run(question)
        # Optionally, you can get the intermediate Cypher and results if you subclass or modify the chain
        # For now, wrap the answer in a Document for downstream use
        return [Document(page_content=answer, metadata={"source": "neo4j_graph", "type": "graph_qa"})]
    except Exception as e:
        logger.warning(f"GraphCypherQAChain failed: {e}")

    # --- Fallback: LLM Cypher generation and manual execution ---
    if use_llm_cypher:
        try:
            cypher = generate_cypher(question, entities, schema)
            logger.info(f"Generated Cypher: {cypher}")
            results = graph.query(cypher)
            docs = format_results_as_documents(results)
            if docs:
                return docs
        except Exception as e:
            logger.warning(f"LLM Cypher generation/execution failed: {e}")

    # --- Fallback: 1-hop neighborhood for each entity (with relationship filtering) ---
    docs = []
    for entity in entities:
        fulltext_query = generate_full_text_query(entity["name"])
        cypher = """
        CALL db.index.fulltext.queryNodes('entity', $query, {limit:2})
        YIELD node,score
        CALL {
          MATCH (node)-[r]->(neighbor)
          WHERE type(r) <> 'MENTIONS'  // Filter out non-informative relations
          RETURN node.name + ' - ' + type(r) + ' -> ' + neighbor.name + coalesce(' (source: ' + neighbor.source + ')', '') AS output
          UNION
          MATCH (node)<-[r]-(neighbor)
          WHERE type(r) <> 'MENTIONS'
          RETURN neighbor.name + ' - ' + type(r) + ' -> ' +  node.name + coalesce(' (source: ' + node.source + ')', '') AS output
        }
        RETURN output LIMIT 50
        """
        response = graph.query(cypher, {"query": fulltext_query})
        for el in response:
            docs.append(Document(page_content=el.get("output", str(el)), metadata={"entity": entity["name"], "source": "neo4j_graph", "type": "1hop_fallback"}))
    return docs


# --- LangChain Runnable Retriever ---
def get_graph_retriever():
    return RunnableLambda(lambda inputs: {"documents": graph_rag_retrieve(inputs["question"]) if isinstance(inputs, dict) and "question" in inputs else graph_rag_retrieve(str(inputs))})


# Example usage:
# docs = graph_rag_retrieve("Who is Elizabeth I?")
# for doc in docs:
#     print(doc.page_content, doc.metadata)
