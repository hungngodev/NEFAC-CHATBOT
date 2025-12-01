from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    HYDE_GENERATE_FINAL_RESPONSE,
    HYDE_GENERATE_HYPOTHETICAL_DOCUMENT,
    HYDE_RETRIEVE_SUBGRAPH,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState
from src.utils.model_factory import init_model

# Remove premature LLM construction; use per-call configuration with streaming disabled


# --- Subgraph State ---
class HydeState(QueryTransformerState):
    """State for the HyDE query transformation subgraph."""

    hypothetical_document: str = ""
    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
async def generate_hypothetical_document_node(state: HydeState, config: RunnableConfig) -> dict:
    """Generates a hypothetical document and passes it to the retrieval subgraph."""
    question = state["transformed_query"]

    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.hyde_model, disable_streaming=configuration.disable_streaming)

    prompt = ChatPromptTemplate.from_template(configuration.hyde_generation_prompt)
    chain = prompt | llm | StrOutputParser()

    hypothetical_document = await chain.ainvoke({"question": question})
    return {"retrieval_query": hypothetical_document}


async def generate_final_response_node(state: HydeState, config: RunnableConfig) -> dict:
    """Generates the final response using the retrieved documents."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.hyde_model, disable_streaming=configuration.disable_streaming)

    question = state["transformed_query"]
    documents = state["documents"]
    context = format_docs(documents)

    response_prompt = ChatPromptTemplate.from_template(configuration.hyde_final_prompt)
    chain = response_prompt | llm | StrOutputParser()

    final_response = await chain.ainvoke({"question": question, "context": context})

    return {"transformed_context": final_response}


workflow = StateGraph(HydeState)

workflow.add_node(
    HYDE_GENERATE_HYPOTHETICAL_DOCUMENT,
    generate_hypothetical_document_node,
    metadata={
        "description": "Generates hypothetical document using HyDE technique for better retrieval",
        "dependencies": ["transformed_query"],
        "outputs": ["retrieval_query"],
        "strategy": "hypothetical_document_embeddings",
        "expected_duration": "3-6s",
        "model_type": "hyde_model",
        "technique": "document_generation",
    },
)

workflow.add_node(
    HYDE_RETRIEVE_SUBGRAPH,
    retrieval_subgraph,
    metadata={
        "description": "Retrieval subgraph for HyDE strategy using hypothetical document embeddings",
        "dependencies": ["retrieval_query"],
        "outputs": ["documents"],
        "strategy": "multi_strategy_retrieval",
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "embedding_type": "hypothetical_document",
    },
)

workflow.add_node(
    HYDE_GENERATE_FINAL_RESPONSE,
    generate_final_response_node,
    metadata={
        "description": "Generates final response combining hypothetical document with retrieved context",
        "dependencies": ["documents", "transformed_query"],
        "outputs": ["transformed_context"],
        "strategy": "hyde_synthesis",
        "expected_duration": "2-5s",
        "model_type": "hyde_model",
        "response_type": "context_synthesis",
    },
)

workflow.add_edge(START, HYDE_GENERATE_HYPOTHETICAL_DOCUMENT)
workflow.add_edge(HYDE_GENERATE_HYPOTHETICAL_DOCUMENT, HYDE_RETRIEVE_SUBGRAPH)
workflow.add_edge(HYDE_RETRIEVE_SUBGRAPH, HYDE_GENERATE_FINAL_RESPONSE)
workflow.add_edge(HYDE_GENERATE_FINAL_RESPONSE, END)

hyde = workflow.compile(
    debug=True,
    name="hyde_strategy_sequence",
)
