"""
Graph-based retrieval using Neo4j knowledge graph.
Refactored to use the new modular approach with intelligent sub-tool selection.
"""

import os
from typing import List, Optional

from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph

from backend.src.config.node_names import GRAPH_RETRIEVAL_GRAPH_TOOL_NODE
from backend.src.config.settings import Configuration
from backend.src.schemas.state import AgentState


@tool(tags=[GRAPH_RETRIEVAL_GRAPH_TOOL_NODE])
def graph_tool_node(query: str, state: Optional[AgentState] = None, config: RunnableConfig = None) -> List[Document]:
    """
    Intelligent graph tool node that analyzes the query and decides which graph sub-tools to invoke.

    Based on query complexity and type, it will:
    - Use _structured_graph_query for direct Cypher queries
    - Use _statistical_graph_query for aggregation/counting queries
    - Use _graph_rag_search for general relationship queries
    """
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.retriever_worker_model)

    NEO4J_URI = os.environ["NEO4J_URI"]
    NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
    NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)

    cypher_prompt = ChatPromptTemplate.from_template(configuration.cypher_generation_template)
    qa_prompt = ChatPromptTemplate.from_template(configuration.graph_qa_prompt)

    # Instantiate the GraphCypherQAChain with enhanced configuration
    graph_qa_chain = GraphCypherQAChain.from_llm(llm, graph=graph, verbose=True, cypher_prompt=cypher_prompt, qa_prompt=qa_prompt, validate_cypher=True, return_intermediate_steps=True)

    # Invoke the chain with the combined question and entities
    result = graph_qa_chain.invoke({"query": state["contextualized_query"]})

    intermediate_steps = result.get("intermediate_steps", [])
    final_result = result.get("result", "")

    metadata = {"source": "graph_cypher_qa", "retrieval_method": "graph_rag_chain", "cypher_query": intermediate_steps[0].get("query") if intermediate_steps and isinstance(intermediate_steps[0], dict) else "Unknown", "intermediate_steps": intermediate_steps}
    documents = [Document(page_content=final_result, metadata=metadata)]

    return documents
