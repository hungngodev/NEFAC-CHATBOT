import logging
import os
from typing import Any, Dict, List, Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_neo4j import Neo4jGraph  # Modern import
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.constant import MODEL_NAME

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Neo4j Graph Connection ---
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)

# --- LLM Setup ---

llm = ChatOpenAI(temperature=0, model=MODEL_NAME)


# --- Entity Extraction Schema ---
class Entities(BaseModel):
    names: List[str] = Field(..., description="Canonical entity names (person, org, etc.) in the text.")
    types: Optional[List[str]] = Field(None, description="Entity types (Person, Organization, etc.)")


# --- Entity Extraction Chain ---
entity_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extract canonical entities (with type if possible) from the text. Return as JSON.",
        ),
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


# --- Graph Schema Fetching (Static, Dynamic, or Extended) ---
def get_graph_schema(use_dynamic_schema: bool = False, extend_with_dynamic: bool = False) -> str:
    """
    Returns the graph schema as a string.
    - If use_dynamic_schema is True, fetch from Neo4j.
    - If extend_with_dynamic is True, merge static and dynamic schemas.
    - Otherwise, return static NEFAC schema.
    """
    static_schema = """
Labels: Person, Organization, Case, Statute
Properties:
 - Person: name, role, affiliation
 - Organization: name, type
 - Case: name, citation, decisionDate
 - Statute: title, section
Relationships:
 - FILED_BY (Case -> Organization)
 - CITED_IN (Statute -> Case)
 - DECIDED_BY (Case -> Person)
 - AMICUS_BRIEF_BY (Case -> Organization)
 - MENTIONS (any -> any)
"""
    if use_dynamic_schema or extend_with_dynamic:
        try:
            dynamic_schema = str(graph.get_schema)
            if extend_with_dynamic:
                return static_schema + "\n\n--- Dynamic Schema Extension ---\n" + dynamic_schema
            return dynamic_schema
        except Exception as e:
            logger.warning(f"Could not fetch dynamic schema: {e}")
            # Fallback to static
    return static_schema


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
        return re.sub(r"[+\-!(){}\[\]^\"~*?:\\/]|&&|\||", "", s)

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
You are a Neo4j Cypher expert. Your task is to generate an efficient and accurate Cypher query to answer the given question, utilizing the provided graph schema and identified entities. Focus on returning only the Cypher statement, without any additional text or explanations.

**Instructions for Cypher Generation:**
1.  **Prioritize Graph Traversal:** Whenever possible, use graph patterns (MATCH, OPTIONAL MATCH) to find relationships between entities.
2.  **Use Properties:** Filter nodes and relationships using their properties (e.g., `n.name = '...'`, `r.date > '...'`).
3.  **Aggregations:** Use aggregation functions (e.g., `COUNT`, `SUM`, `AVG`, `COLLECT`) when the question implies a summary or count.
4.  **Pathfinding:** For questions asking about connections or relationships between two entities, consider `shortestPath` or `allShortestPaths`.
5.  **Filtering:** Apply `WHERE` clauses to narrow down results based on conditions in the question.
6.  **Ordering and Limiting:** Use `ORDER BY` and `LIMIT` for structured results, especially if the question asks for "top N" or "most recent."
7.  **Return Relevant Data:** Ensure the `RETURN` clause includes all necessary information to answer the question.
8.  **Schema Adherence:** Strictly adhere to the provided schema for node labels, relationship types, and properties.
9.  **No Explanations:** Only output the Cypher query.

Schema:
{schema}

Cypher examples:
# Find all organizations NEFAC has partnered with and the nature of their partnership.
MATCH (n:Organization {{name: 'NEFAC'}})-[r:PARTNERS_WITH]->(p:Organization)
RETURN p.name AS Partner, type(r) AS PartnershipType

# List all events hosted by NEFAC in 2023.
MATCH (e:Event)-[:HOSTED_BY]->(o:Organization {{name: 'NEFAC'}})
WHERE e.date STARTS WITH '2023'
RETURN e.name AS EventName, e.date AS EventDate

# What legal cases is 'John Doe' involved in, and in what capacity?
MATCH (p:Person {{name: 'John Doe'}})-[r]-(c:Case)
RETURN c.name AS CaseName, type(r) AS Role

# Find the shortest path between 'NEFAC' and 'ACLU'.
MATCH p = shortestPath((n1:Organization {{name: 'NEFAC'}})-[*..5]-(n2:Organization {{name: 'ACLU'}}))
RETURN p

# Count the number of articles published by 'Jane Smith'.
MATCH (a:Article)-[:AUTHORED_BY]->(p:Person {{name: 'Jane Smith'}})
RETURN COUNT(a) AS NumberOfArticles

# Which statutes are cited in cases decided by 'Supreme Court'?
MATCH (s:Statute)-[:CITED_IN]->(c:Case)-[:DECIDED_BY]->(o:Organization {{name: 'Supreme Court'}})
RETURN s.title, s.citation

# What are the names of all staff members of NEFAC and their titles?
MATCH (p:Person)-[:WORKS_FOR]->(o:Organization {{name: 'NEFAC'}})
WHERE 'StaffMember' IN labels(p)
RETURN p.name AS StaffMemberName, p.title AS Title

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
def extract_paths_between_entities(entities: List[Dict[str, str]], max_hops: int = 3) -> List[str]:
    """
    Build Cypher shortestPath queries between each pair of entities.
    """
    cyphers: List[str] = []
    for i, e1 in enumerate(entities):
        for j, e2 in enumerate(entities):
            if i < j:
                cyphers.append(f"MATCH path = shortestPath((a:__Entity__ {{name: '{e1['name']}'}})-[*..{max_hops}]-(b:__Entity__ {{name: '{e2['name']}'}})) " "RETURN path LIMIT 3")
    return cyphers


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


# --- Entity Information Retrieval ---
def get_detailed_entity_info(entity_name: str) -> Optional[Document]:
    """
    Retrieves detailed information about a specific entity from the graph,
    including its properties and direct relationships.
    """
    cypher_query = """
    MATCH (n)
    WHERE n.name = $entity_name OR n.title = $entity_name
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN
        n.name AS entityName,
        labels(n) AS entityLabels,
        properties(n) AS entityProperties,
        collect({
            relationshipType: type(r),
            targetNodeName: coalesce(m.name, m.title),
            targetNodeLabels: labels(m),
            relationshipProperties: properties(r)
        }) AS outgoingRelationships,
        collect({
            relationshipType: type(r),
            sourceNodeName: coalesce(m.name, m.title),
            sourceNodeLabels: labels(m),
            relationshipProperties: properties(r)
        }) AS incomingRelationships
    LIMIT 1
    """
    try:
        result = graph.query(cypher_query, {"entity_name": entity_name})
        if result and result[0]:
            info = result[0]
            content_parts = []
            content_parts.append(f"Entity: {info['entityName']} ({', '.join(info['entityLabels'])})")

            if info["entityProperties"]:
                content_parts.append("Properties:")
                for k, v in info["entityProperties"].items():
                    content_parts.append(f"  {k}: {v}")

            if info["outgoingRelationships"]:
                content_parts.append("Outgoing Relationships:")
                for rel in info["outgoingRelationships"]:
                    if rel["relationshipType"]:  # Ensure relationship exists
                        content_parts.append(f"  - {rel['relationshipType']} -> {rel['targetNodeName']} ({', '.join(rel['targetNodeLabels'])})")
                        if rel["relationshipProperties"]:
                            content_parts.append(f"    Rel Properties: {rel['relationshipProperties']}")

            if info["incomingRelationships"]:
                content_parts.append("Incoming Relationships:")
                for rel in info["incomingRelationships"]:
                    if rel["relationshipType"]:  # Ensure relationship exists
                        content_parts.append(f"  - {rel['sourceNodeName']} ({', '.join(rel['sourceNodeLabels'])}) - {rel['relationshipType']} ->")
                        if rel["relationshipProperties"]:
                            content_parts.append(f"    Rel Properties: {rel['relationshipProperties']}")

            return Document(
                page_content="\n".join(content_parts),
                metadata={
                    "entity": entity_name,
                    "source": "neo4j_graph_detailed_info",
                    "type": "entity_description",
                    "labels": info["entityLabels"],
                    "properties": info["entityProperties"],
                },
            )
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve detailed entity info for {entity_name}: {e}")
        return None


# Example usage:
# docs = graph_rag_retrieve("Who is Elizabeth I?")
# for doc in docs:
#     print(doc.page_content, doc.metadata)
