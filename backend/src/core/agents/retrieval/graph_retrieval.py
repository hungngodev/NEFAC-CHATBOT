"""
Graph-based retrieval using Neo4j knowledge graph.
Refactored to use the new modular approach with intelligent sub-tool selection.
"""

import os

from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph

from src.config.settings import Configuration

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER")
if not NEO4J_USERNAME:
    raise KeyError("NEO4J_USERNAME")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)


@tool()
async def graph_tool_node(query: str, conf: Configuration | None = None) -> list[Document]:
    """
    Intelligent graph tool node that analyzes the query and decides which graph sub-tools to invoke.

    Based on query complexity and type, it will:
    - Use _structured_graph_query for direct Cypher queries
    - Use _statistical_graph_query for aggregation/counting queries
    - Use _graph_rag_search for general relationship queries
    """
    configuration = conf or Configuration.from_runnable_config(None)
    llm = init_chat_model(configuration.retriever_worker_model, disable_streaming=configuration.disable_streaming)

    cypher_prompt = ChatPromptTemplate.from_template(configuration.cypher_generation_template)
    qa_prompt = ChatPromptTemplate.from_template(configuration.graph_qa_prompt)

    # Instantiate the GraphCypherQAChain with enhanced configuration
    graph_qa_chain = GraphCypherQAChain.from_llm(
        llm,
        graph=graph,
        verbose=True,
        cypher_prompt=cypher_prompt,
        qa_prompt=qa_prompt,
        validate_cypher=True,
        return_intermediate_steps=True,
        allow_dangerous_requests=True,
    )

    # Invoke the chain with the combined question and entities
    query_text = query
    try:
        result = await graph_qa_chain.ainvoke({"query": query_text})
    except Exception as e:
        # Fallback: retry with a stricter cypher prompt to avoid invalid aliases/keywords
        strict_suffix = "\n\nADDITIONAL STRICT RULES (retry):\n- Absolutely no spaces or non-ASCII characters in RETURN aliases.\n- Never include non-English words anywhere in the query.\n- If you need to combine words, use camelCase or snake_case (e.g., dateFiledOrDocketed).\n- Output a single valid Cypher query only."
        strict_template = f"{configuration.cypher_generation_template}{strict_suffix}"
        strict_cypher_prompt = ChatPromptTemplate.from_template(strict_template)
        graph_qa_chain_strict = GraphCypherQAChain.from_llm(
            llm,
            graph=graph,
            verbose=True,
            cypher_prompt=strict_cypher_prompt,
            qa_prompt=qa_prompt,
            validate_cypher=True,
            return_intermediate_steps=True,
            allow_dangerous_requests=True,
        )
        try:
            result = await graph_qa_chain_strict.ainvoke({"query": query_text})
        except Exception:
            # Re-raise the original exception to preserve debugging context
            raise e

    intermediate_steps = result.get("intermediate_steps", [])
    final_result = result.get("result", "")

    metadata = {"source": "graph_cypher_qa", "retrieval_method": "graph_rag_chain", "cypher_query": intermediate_steps[0].get("query") if intermediate_steps and isinstance(intermediate_steps[0], dict) else "Unknown", "intermediate_steps": intermediate_steps}
    documents = [Document(page_content=final_result, metadata=metadata)]

    return documents
