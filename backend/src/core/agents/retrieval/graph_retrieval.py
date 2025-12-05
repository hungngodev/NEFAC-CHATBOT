import os

from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph

from src.config.settings import Configuration
from src.utils.model_factory import init_model

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER")
if not NEO4J_USERNAME:
    raise KeyError("NEO4J_USERNAME")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)


@tool(description="Performs graph-based retrieval using Neo4j Cypher queries.")
async def graph_tool_node(query: str, conf: Configuration | None = None) -> list[Document]:

    configuration = conf or Configuration.from_runnable_config(None)
    llm = init_model(configuration.retriever_worker_model, disable_streaming=configuration.disable_streaming)

    cypher_prompt = ChatPromptTemplate.from_template(configuration.cypher_generation_template)
    qa_prompt = ChatPromptTemplate.from_template(configuration.graph_qa_prompt)

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

    query_text = query
    result = await graph_qa_chain.ainvoke({"query": query_text})

    intermediate_steps = result.get("intermediate_steps", [])
    final_result = result.get("result", "")

    metadata = {"source": "graph_cypher_qa", "retrieval_method": "graph_rag_chain", "cypher_query": intermediate_steps[0].get("query") if intermediate_steps and isinstance(intermediate_steps[0], dict) else "Unknown", "intermediate_steps": intermediate_steps}
    documents = [Document(page_content=final_result, metadata=metadata)]

    return documents
