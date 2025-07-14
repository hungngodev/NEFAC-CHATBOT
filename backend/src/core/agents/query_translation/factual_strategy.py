from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from src.config.prompts import FACTUAL_STRATEGY_PROMPT
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState


# --- Subgraph State ---
class FactualStrategyState(AgentState):
    """State for the factual strategy subgraph."""

    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
def generate_factual_query_node(state: FactualStrategyState, llm) -> RetrievalSubgraphState:
    """Generates a factual query and passes it to the retrieval subgraph."""
    question = state["contextualized_query"]

    prompt = ChatPromptTemplate.from_template(FACTUAL_STRATEGY_PROMPT)
    chain = prompt | llm | StrOutputParser()

    factual_query = chain.invoke({"question": question})
    # Pass the new query to the retrieval subgraph
    return {"retrieval_query": factual_query}


def format_documents_node(state: FactualStrategyState) -> AgentState:
    """Formats the retrieved documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"final_context": formatted_string}


workflow = StateGraph(FactualStrategyState)

workflow.add_node("generate_factual_query", generate_factual_query_node)
workflow.add_node("retrieve_subgraph", retrieval_subgraph)
workflow.add_node("format_documents", format_documents_node)

workflow.set_entry_point("generate_factual_query")
workflow.add_edge("generate_factual_query", "retrieve_subgraph")
workflow.add_edge("retrieve_subgraph", "format_documents")
workflow.add_edge("format_documents", END)

factual_strategy = workflow.compile()
