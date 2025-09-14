"""
Decomposition query transformation agent.
Breaks down complex queries into sub-questions for better retrieval.
"""

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

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
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class DecompositionState(QueryTransformerState):
    """State for the decomposition query transformation subgraph."""

    sub_questions: list[str] = []
    q_a_pairs: list[str] = []


# --- Nodes ---
async def generate_sub_questions_node(state: DecompositionState, config: RunnableConfig) -> DecompositionState:
    """Decomposes the main question into a series of sub-questions."""
    configuration = Configuration.from_runnable_config(config)

    model = init_chat_model(configuration.decomposition_generate_model, disable_streaming=configuration.disable_streaming)
    question = state["transformed_query"]

    prompt = ChatPromptTemplate.from_template(configuration.decomposition_generate_prompt)
    chain = prompt | model | StrOutputParser() | (lambda x: x.strip().split("\n"))

    sub_questions = await chain.ainvoke({"question": question})
    sub_questions = [q.strip() for q in sub_questions if q.strip()]

    return {"sub_questions": sub_questions}


def answer_sub_questions_node(state: DecompositionState) -> RetrievalSubgraphState:
    """Answers each sub-question iteratively, using retrieval for context."""
    sub_questions = state.get("sub_questions", [])
    q_a_pairs = state.get("q_a_pairs", [])
    current_index = len(q_a_pairs)

    sub_question = sub_questions[current_index]
    return {"retrieval_query": sub_question}


async def format_answer_node(state: DecompositionState, config: RunnableConfig) -> DecompositionState:
    """Format the answer for the current sub-question."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.decomposition_answer_model, disable_streaming=configuration.disable_streaming)

    context_docs = state["documents"]
    context = format_docs(context_docs)
    # Accumulate Q&A pairs across iterations to advance the loop index
    q_a_pairs = state.get("q_a_pairs", [])
    previous_q_a = "\n---\n".join(q_a_pairs)

    qa_prompt = ChatPromptTemplate.from_template(configuration.decomposition_qa_template)
    sub_questions = state["sub_questions"]
    sub_question = sub_questions[len(q_a_pairs)]

    qa_chain = qa_prompt | llm | StrOutputParser()
    answer = await qa_chain.ainvoke({"sub_question": sub_question, "q_a_pairs": previous_q_a, "context": context})

    return {"q_a_pairs": q_a_pairs + [f"Question: {sub_question}\nAnswer: {answer}"]}


async def synthesize_final_answer_node(state: DecompositionState, config: RunnableConfig) -> QueryTransformerState:
    """Synthesizes the final answer from the Q&A pairs."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.decomposition_final_model, disable_streaming=configuration.disable_streaming)

    question = state["transformed_query"]
    q_a_pairs_str = "\n---\n".join(state.get("q_a_pairs", []))

    synthesis_prompt = ChatPromptTemplate.from_template(configuration.decomposition_synthesis_template)
    synthesis_chain = synthesis_prompt | llm | StrOutputParser()

    final_response = await synthesis_chain.ainvoke({"context": q_a_pairs_str, "question": question})

    return {"transformed_context": final_response}


def route_from_format_nodes(state: DecompositionState) -> str:
    """Decide whether to loop back to answer next sub-question or proceed to synthesis."""
    if len(state.get("q_a_pairs", [])) < len(state.get("sub_questions", [])):
        return DECOMPOSITION_ANSWER_SUB_QUESTIONS
    else:
        return DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER


workflow = StateGraph(DecompositionState)

workflow.add_node(
    DECOMPOSITION_GENERATE_SUB_QUESTIONS,
    generate_sub_questions_node,
    metadata={
        "description": "Decomposes complex queries into focused sub-questions for iterative retrieval",
        "dependencies": ["transformed_query"],
        "outputs": ["sub_questions"],
        "strategy": "query_decomposition",
        "expected_duration": "2-4s",
        "model_type": "decomposition_generate_model",
        "loop_control": "generates_sub_questions_list",
    },
)

workflow.add_node(
    DECOMPOSITION_ANSWER_SUB_QUESTIONS,
    answer_sub_questions_node,
    metadata={"description": "Prepares retrieval query for current unanswered sub-question", "dependencies": ["sub_questions", "q_a_pairs"], "outputs": ["retrieval_query"], "strategy": "iterative_sub_question_processing", "expected_duration": "0.1-0.5s", "loop_control": "tracks_current_index"},
)

workflow.add_node(
    DECOMPOSITION_FORMAT_ANSWER,
    format_answer_node,
    destinations=[DECOMPOSITION_ANSWER_SUB_QUESTIONS, DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER],
    metadata={
        "description": "Formats answer for current sub-question using retrieved context",
        "dependencies": ["documents", "q_a_pairs", "sub_questions"],
        "outputs": ["q_a_pairs"],
        "strategy": "contextual_qa_formatting",
        "expected_duration": "2-5s",
        "model_type": "decomposition_answer_model",
        "loop_control": "conditional_routing_target",
    },
)

workflow.add_node(
    DECOMPOSITION_RETRIEVE_SUBGRAPH,
    retrieval_subgraph,
    metadata={
        "description": "Retrieval subgraph for decomposition strategy sub-questions",
        "dependencies": ["retrieval_query"],
        "outputs": ["documents"],
        "strategy": "multi_strategy_retrieval",
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "context": "sub_question_focused",
    },
)

workflow.add_node(
    DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER,
    synthesize_final_answer_node,
    metadata={
        "description": "Synthesizes final comprehensive answer from all Q&A pairs",
        "dependencies": ["q_a_pairs", "transformed_query"],
        "outputs": ["transformed_context"],
        "strategy": "qa_synthesis",
        "expected_duration": "3-6s",
        "model_type": "decomposition_final_model",
        "synthesis_method": "contextual_integration",
    },
)

workflow.set_entry_point(DECOMPOSITION_GENERATE_SUB_QUESTIONS)


def _route_after_generate(state: DecompositionState) -> str:
    """If no sub-questions were generated, skip directly to synthesis."""
    return DECOMPOSITION_ANSWER_SUB_QUESTIONS if len(state.get("sub_questions", [])) > 0 else DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER


workflow.add_conditional_edges(DECOMPOSITION_GENERATE_SUB_QUESTIONS, _route_after_generate)
workflow.add_edge(DECOMPOSITION_ANSWER_SUB_QUESTIONS, DECOMPOSITION_RETRIEVE_SUBGRAPH)
workflow.add_edge(DECOMPOSITION_RETRIEVE_SUBGRAPH, DECOMPOSITION_FORMAT_ANSWER)
workflow.add_conditional_edges(DECOMPOSITION_FORMAT_ANSWER, route_from_format_nodes)
workflow.add_edge(DECOMPOSITION_SYNTHESIZE_FINAL_ANSWER, END)

decomposition = workflow.compile(
    debug=True,
    name="decomposition_strategy_loop",
)
