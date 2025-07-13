"""
Graph-based retrieval using Neo4j knowledge graph.
Refactored to use the new modular approach with intelligent sub-tool selection.
"""

import logging
import os
from typing import List, Optional

from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_openai import ChatOpenAI

from src.config.constant import RETRIEVAL_MODEL_NAME
from src.schemas.core_types import AgentState

logger = logging.getLogger(__name__)

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)

# --- LLM Setup ---
llm = ChatOpenAI(temperature=0, model=RETRIEVAL_MODEL_NAME)

CYPHER_GENERATION_TEMPLATE = """You are a Neo4j Cypher expert. Your task is to generate an efficient and accurate Cypher query to answer the given question, utilizing the provided graph schema. Focus on returning only the Cypher statement, without any additional text or explanations.

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

Question: {question}"""


@tool
def graph_tool_node(query: str, state: Optional[AgentState] = None) -> List[Document]:
    """
    Intelligent graph tool node that analyzes the query and decides which graph sub-tools to invoke.

    Based on query complexity and type, it will:
    - Use _structured_graph_query for direct Cypher queries
    - Use _statistical_graph_query for aggregation/counting queries
    - Use _graph_rag_search for general relationship queries
    """

    cypher_prompt = ChatPromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)

    # Define a QA prompt for synthesizing the answer from the graph query result.
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Given a question and context from a knowledge graph, answer the question clearly and concisely. Use only the provided context. If the context is empty or does not contain the answer, state that you could not find the information in the knowledge graph.",
            ),
            ("human", "Question: {question}\nContext: {context}"),
        ]
    )

    # Instantiate the GraphCypherQAChain with enhanced configuration
    graph_qa_chain = GraphCypherQAChain.from_llm(llm, graph=graph, verbose=True, cypher_prompt=cypher_prompt, qa_prompt=qa_prompt, validate_cypher=True, return_intermediate_steps=True)

    # Invoke the chain with the combined question and entities
    result = graph_qa_chain.invoke({"query": state["contextualized_query"]})

    intermediate_steps = result.get("intermediate_steps", [])
    final_result = result.get("result", "")

    metadata = {"source": "graph_cypher_qa", "retrieval_method": "graph_rag_chain", "cypher_query": intermediate_steps[0].get("query") if intermediate_steps and isinstance(intermediate_steps[0], dict) else "Unknown", "intermediate_steps": intermediate_steps}
    documents = [Document(page_content=final_result, metadata=metadata)]

    # Add metadata tags
    for doc in documents:
        if not hasattr(doc, "metadata") or doc.metadata is None:
            doc.metadata = {}
        doc.metadata["stream_tag"] = "graph_retrieved_docs"
        doc.metadata["retrieval_method"] = "graph_search"

    return documents
