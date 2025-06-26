import os
from langchain_community.graphs import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
import logging


def graph_rag_ingest(documents):
    """
    Ingests a list of LangChain Document objects into Neo4j as a knowledge graph using LLMGraphTransformer.
    Follows best practices from the LangChain blog:
    https://blog.langchain.com/enhancing-rag-based-applications-accuracy-by-constructing-and-leveraging-knowledge-graphs/
    - Requires NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, and OPENAI_API_KEY to be set in the environment.
    - Uses OpenAI GPT-4 Turbo for graph extraction.
    - Adds baseEntityLabel and include_source for optimal graph structure and traceability.
    """
    logger = logging.getLogger(__name__)
    required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "OPENAI_API_KEY"]
    for var in required_vars:
        if not os.environ.get(var):
            raise EnvironmentError(f"Missing required environment variable: {var}")

    graph = Neo4jGraph()
    llm = ChatOpenAI(temperature=0, model="gpt-4-turbo")
    llm_transformer = LLMGraphTransformer(llm=llm)

    # Convert to graph documents
    graph_documents = llm_transformer.convert_to_graph_documents(documents)

    # Store in Neo4j with best-practice flags
    graph.add_graph_documents(
        graph_documents, baseEntityLabel=True, include_source=True
    )
    logger.info("Graph RAG ingestion complete.")
