from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

CONTEXTUAL_STRATEGY_PROMPT = """
You are an expert at understanding implied context in user queries, specifically in the domain of First Amendment rights, freedom of information, and government transparency as covered by nefac.org. For a given factual query, infer what background information, historical context, regional relevance (New England), or legal/policy themes might be implied but not explicitly stated. Focus on what contextual understanding would best support retrieval and accurate answering.
Return ONLY a brief description of the implied context without any explanation.
"""


# --- Subgraph State ---
class ContextualStrategyState(AgentState):
    """State for the contextual strategy subgraph."""

    # The 'documents' field will be populated by the retrieval subgraph


llm = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)


# --- Nodes ---
def generate_contextual_query_node(state: ContextualStrategyState) -> dict:
    """Generates a contextual query and passes it to the retrieval subgraph."""
    question = state["contextualized_query"]

    prompt = ChatPromptTemplate.from_template(CONTEXTUAL_STRATEGY_PROMPT)
    chain = prompt | llm | StrOutputParser()

    contextual_query = chain.invoke({"question": question})
    # Pass the new query to the retrieval subgraph
    return {"retrieval_query": contextual_query}


def format_documents_node(state: ContextualStrategyState) -> dict:
    """Formats the retrieved documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"final_context": formatted_string}


workflow = StateGraph(ContextualStrategyState)

workflow.add_node("generate_contextual_query", generate_contextual_query_node)
workflow.add_node("retrieve_subgraph", retrieval_subgraph)
workflow.add_node("format_documents", format_documents_node)

workflow.set_entry_point("generate_contextual_query")
workflow.add_edge("generate_contextual_query", "retrieve_subgraph")
workflow.add_edge("retrieve_subgraph", "format_documents")
workflow.add_edge("format_documents", END)

contextual_strategy = workflow.compile()
