"""
Decomposition query transformation agent.
Breaks down complex queries into sub-questions for better retrieval.
"""

from typing import List

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph import END, StateGraph

from src.config.node_names import (
    DECOMPOSITION_ANSWER_SUB_QUESTIONS,
    DECOMPOSITION_FORMAT_ANSWER,
    DECOMPOSITION_GENERATE_SUB_QUESTIONS,
    DECOMPOSITION_RETRIEVE_SUBGRAPH,
    DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState


# --- Subgraph State ---
class DecompositionState(AgentState):
    """State for the decomposition query transformation subgraph."""

    sub_questions: List[str] = []
    q_a_pairs: List[str] = []


# --- Nodes ---
def generate_sub_questions_node(state: DecompositionState, config: RunnableConfig) -> DecompositionState:
    """Decomposes the main question into a series of sub-questions."""
    # Get configuration from RunnableConfig
    configuration = Configuration.from_runnable_config(config)

    model = init_chat_model(configuration.decomposition_generate_model)
    question = state["contextualized_query"]

    # Use prompt from configuration
    prompt = ChatPromptTemplate.from_template(configuration.decomposition_generate_prompt)
    chain = prompt | model | StrOutputParser() | (lambda x: x.strip().split("\n"))

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


def format_answer_node(state: DecompositionState, config: RunnableConfig) -> DecompositionState:
    """Format the answer for the current sub-question."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.decomposition_answer_model)

    context_docs = state["documents"]
    context = format_docs(context_docs)
    q_a_pairs = state["q_a_pairs"]
    previous_q_a = "\n---\n".join(q_a_pairs)

    qa_prompt = ChatPromptTemplate.from_template(configuration.decomposition_qa_template)
    sub_questions = state["sub_questions"]
    sub_question = sub_questions[len(q_a_pairs)]  # Next unanswered sub-question

    qa_chain = qa_prompt | llm | StrOutputParser()
    answer = qa_chain.invoke({"sub_question": sub_question, "q_a_pairs": previous_q_a, "context": context})

    return {"q_a_pairs": [f"Question: {sub_question}\nAnswer: {answer}"]}


def synthesize_final_answer_node(state: DecompositionState, config: RunnableConfig) -> AgentState:
    """Synthesizes the final answer from the Q&A pairs."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.decomposition_final_model)

    question = state["contextualized_query"]
    q_a_pairs_str = "\n---\n".join(state["q_a_pairs"])

    synthesis_prompt = ChatPromptTemplate.from_template(configuration.decomposition_synthesis_template)
    synthesis_chain = synthesis_prompt | llm | StrOutputParser()

    final_response = synthesis_chain.invoke({"context": q_a_pairs_str, "question": question})

    return {"final_context": final_response}


def route_from_format_nodes(state: DecompositionState) -> str:
    """Decide whether to loop back to answer next sub-question or proceed to synthesis."""
    if len(state["q_a_pairs"]) < len(state["sub_questions"]):
        return DECOMPOSITION_ANSWER_SUB_QUESTIONS  # More to answer, loop back
    else:
        return DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER  # All done, proceed to synthesis


# --- Workflow ---
workflow = StateGraph(DecompositionState)

# Add nodes
workflow.add_node(DECOMPOSITION_GENERATE_SUB_QUESTIONS, generate_sub_questions_node)
# Note: This node now loops internally, invoking retrieval for each sub-question.
# A more complex graph could unroll this loop, but this is simpler.
workflow.add_node(DECOMPOSITION_ANSWER_SUB_QUESTIONS, answer_sub_questions_node)
workflow.add_node(DECOMPOSITION_FORMAT_ANSWER, format_answer_node)  # Intermediate formatting step
workflow.add_node(DECOMPOSITION_RETRIEVE_SUBGRAPH, retrieval_subgraph)
workflow.add_node(DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER, synthesize_final_answer_node)

# Add edges
workflow.set_entry_point(DECOMPOSITION_GENERATE_SUB_QUESTIONS)
workflow.add_edge(DECOMPOSITION_GENERATE_SUB_QUESTIONS, DECOMPOSITION_ANSWER_SUB_QUESTIONS)
workflow.add_edge(DECOMPOSITION_ANSWER_SUB_QUESTIONS, DECOMPOSITION_RETRIEVE_SUBGRAPH)
workflow.add_edge(DECOMPOSITION_RETRIEVE_SUBGRAPH, DECOMPOSITION_FORMAT_ANSWER)
workflow.add_conditional_edge(DECOMPOSITION_FORMAT_ANSWER, route_from_format_nodes)  # Loop back to answer next
workflow.add_edge(DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER, END)

# Compile the workflow
decomposition = workflow.compile()
