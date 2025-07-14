from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import BASE_PROMPT
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

HYDE_GENERATION_PROMPT = f"""
You are an AI assistant specialized in legal and First Amendment topics for the New England First Amendment Coalition (NEFAC).

To effectively retrieve relevant case studies, legal analyses, press freedom guides, and related NEFAC resources from our vector database, generate a hypothetical, concise, and informative legal passage that could directly address the user's question.
{BASE_PROMPT} 

The synthesized passage should:
- Clearly resemble a NEFAC-authored case analysis, legal summary, or practical guidance document.
- Include specific legal terminology, relevant case precedents, or practical implications where applicable.
- Be focused, authoritative, and realistic enough to effectively query our document and transcript database.

User Question: {{question}}

Synthesized Legal Passage:
"""
# ============================================================================
# HYDE FINAL PROMPT
# ============================================================================
HYDE_FINAL_PROMPT = """
Answer the following question based on the NEFAC-related documents and resources provided below:

{context}

Question: {question}
"""
llm = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)


# --- Subgraph State ---
class HydeState(AgentState):
    """State for the HyDE query transformation subgraph."""

    hypothetical_document: str = ""
    # The 'documents' field will be populated by the retrieval subgraph


# --- Nodes ---
def generate_hypothetical_document_node(state: HydeState) -> RetrievalSubgraphState:
    """Generates a hypothetical document to be used as the retrieval query."""
    question = state["contextualized_query"]

    hyde_prompt = ChatPromptTemplate.from_template(HYDE_GENERATION_PROMPT)
    chain = hyde_prompt | llm | StrOutputParser()

    hypothetical_document = chain.invoke({"question": question})
    # Pass the hypothetical document to the retrieval subgraph via the 'retrieval_query' field
    return {"retrieval_query": hypothetical_document}


def generate_final_response_node(state: HydeState) -> AgentState:
    """Generates a final response using the documents retrieved based on the HyDE query."""
    question = state["contextualized_query"]
    # The retrieval subgraph has already populated the 'documents' field
    documents = state["documents"]

    context = format_docs(documents)

    final_prompt = ChatPromptTemplate.from_template(HYDE_FINAL_PROMPT)
    chain = final_prompt | llm | StrOutputParser()

    final_response = chain.invoke({"context": context, "question": question})
    return {"final_context": final_response}


workflow = StateGraph(HydeState)

workflow.add_node("generate_hypothetical_document", generate_hypothetical_document_node)
# The retrieval subgraph is now a single, atomic node in this workflow
workflow.add_node("retrieve_subgraph", retrieval_subgraph)
workflow.add_node("generate_final_response", generate_final_response_node)

workflow.set_entry_point("generate_hypothetical_document")
workflow.add_edge("generate_hypothetical_document", "retrieve_subgraph")
workflow.add_edge("retrieve_subgraph", "generate_final_response")
workflow.add_edge("generate_final_response", END)

hyde = workflow.compile()
