from operator import add
from typing import Annotated, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import BASE_PROMPT
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

DECOMPOSITION_PROMPT = f"""
You are an expert assistant for the New England First Amendment Coalition (NEFAC). Your role is to break down the user's complex question into exactly 3 focused, independently-answerable sub-questions to retrieve precise documents from our vector database of legal analyses, FOI guides, press-freedom resources, and relevant transcripts.
{BASE_PROMPT}
The sub-questions should:
1. Address specific legal rights, frameworks, or procedures relevant to the original question.
2. Identify related historical cases, precedents, or contextual background crucial to the topic.
3. Explore practical applications, examples, or implications for journalists or citizens in New England.

Original question: {{question}}

Output (exactly 3 queries, one per line):
"""

FINAL_SYNTHESIS_TEMPLATE = """
    You are a NEFAC legal expert. Given the following sub-questions and answers:
    {context}

    Synthesize a cohesive, comprehensive response to the user's main question:
    {question}
    """

QA_TEMPLATE = """
You are a NEFAC legal expert answering the following sub-question:
--- 
{sub_question}
---

Background information (previously answered sub-questions):
---
{q_a_pairs}
---

Additional relevant NEFAC context:
---
{context}
---

Use the context and background to answer precisely:
{sub_question}
"""
llm = ChatOpenAI(model=QUERY_TRANSLATION_MODEL_NAME, temperature=0)


# --- Subgraph State ---
class DecompositionState(AgentState):
    """State for the decomposition query transformation subgraph."""

    sub_questions: List[str] = []
    q_a_pairs: Annotated[list[str], add]
    # The 'documents' field will be populated by the retrieval subgraph in each loop


# --- Nodes ---
def generate_sub_questions_node(state: DecompositionState) -> DecompositionState:
    """Decomposes the main question into a series of sub-questions."""
    question = state["contextualized_query"]

    prompt = ChatPromptTemplate.from_template(DECOMPOSITION_PROMPT)
    chain = prompt | llm | StrOutputParser() | (lambda x: x.strip().split("\n"))

    sub_questions = chain.invoke({"question": question})
    sub_questions = [q.strip() for q in sub_questions if q.strip()]

    return {"sub_questions": sub_questions}


def answer_sub_questions_node(state: DecompositionState) -> RetrievalSubgraphState:
    """Answers each sub-question iteratively, using retrieval for context."""
    sub_questions = state["sub_questions"]
    q_a_pairs = state["q_a_pairs"]
    current_index = len(q_a_pairs)  # Track how many have been answered so far
    sub_question = sub_questions[current_index]

    return {"retrieval_query": sub_question}  # Pass current q_a_pairs to state for context


def format_answer_node(state: DecompositionState) -> DecompositionState:
    context_docs = state["documents"]
    context = format_docs(context_docs)
    q_a_pairs = state["q_a_pairs"]
    previous_q_a = "\n---\n".join(q_a_pairs)
    qa_prompt = ChatPromptTemplate.from_template(QA_TEMPLATE)
    sub_questions = state["sub_questions"]
    sub_question = sub_questions[len(q_a_pairs)]  # Next unanswered sub-question
    qa_chain = qa_prompt | llm | StrOutputParser()
    answer = qa_chain.invoke({"sub_question": sub_question, "q_a_pairs": previous_q_a, "context": context})

    return {"q_a_pairs": [f"Question: {sub_question}\nAnswer: {answer}"]}


def synthesize_final_answer_node(state: DecompositionState) -> AgentState:
    """Synthesizes the final answer from the Q&A pairs."""
    question = state["contextualized_query"]
    q_a_pairs_str = "\n---\n".join(state["q_a_pairs"])

    synthesis_prompt = ChatPromptTemplate.from_template(FINAL_SYNTHESIS_TEMPLATE)
    synthesis_chain = synthesis_prompt | llm | StrOutputParser()

    final_response = synthesis_chain.invoke({"context": q_a_pairs_str, "question": question})
    return {"final_context": final_response}


workflow = StateGraph(DecompositionState)

workflow.add_node("generate_sub_questions", generate_sub_questions_node)
# Note: This node now loops internally, invoking retrieval for each sub-question.
# A more complex graph could unroll this loop, but this is simpler.
workflow.add_node("answer_sub_questions", answer_sub_questions_node)
workflow.add_node("format_answer", format_answer_node)  # Intermediate formatting step
workflow.add_node("retrieve_subgraph", retrieval_subgraph)
workflow.add_node("synthesize_final_answer", synthesize_final_answer_node)


def route_from_format_nodes(state: DecompositionState) -> str:
    """Decide whether to loop back to answer next sub-question or proceed to synthesis."""
    if len(state["q_a_pairs"]) < len(state["sub_questions"]):
        return "answer_sub_questions"  # More to answer, loop back
    else:
        return "synthesize_final_answer"  # All done, proceed to synthesis


workflow.set_entry_point("generate_sub_questions")
workflow.add_edge("generate_sub_questions", "answer_sub_questions")
workflow.add_edge("answer_sub_questions", "retrieve_subgraph")
workflow.add_edge("retrieve_subgraph", "format_answer")
workflow.add_edge("format_answer", route_from_format_nodes)  # Loop back to answer next
workflow.add_edge("synthesize_final_answer", END)

decomposition = workflow.compile()
