import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, Send, StateGraph

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import BASE_PROMPT
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.core_types import AgentState

logger = logging.getLogger(__name__)

STEP_BACK_SYSTEM_PROMPT = f"""
You are an expert in First Amendment law and public records processes in New England.
Your task is to take a user’s question and “step back” to a broader, more answerable legal framing aligned with NEFAC’s work.
{BASE_PROMPT}
Here are examples of reformulating specific questions into broader legal inquiries:
"""

# ============================================================================
# STEP BACK RESPONSE PROMPT
# ============================================================================
STEP_BACK_RESPONSE_PROMPT = """
Using both the original question and the stepped-back legal context, produce a comprehensive answer based on these sources:

# normal_context (direct retrieval results)
{normal_context}

# step_back_context (retrieved broader context)
{step_back_context}

Original Question: {question}
Answer:
"""
llm = ChatOpenAI(model=QUERY_TRANSLATION_MODEL_NAME)


# --- Subgraph State ---
class StepBackState(AgentState):
    """State for the step-back query transformation subgraph."""

    step_back_question: str = ""
    origina_context: List[Document] = ""
    step_back_context: List[Document] = ""


# --- Nodes ---
def generate_and_dispatch_node(state: StepBackState) -> StepBackState:
    """Generates a step-back question and dispatches retrieval for both questions in parallel."""
    logger.info("Generating step-back question and dispatching parallel retrieval.")
    original_question = state["contextualized_query"]

    examples = [
        {"input": "Can I film police during a protest in Massachusetts?", "output": "What are the legal rights around recording public officials in Massachusetts?"},
        {"input": "How do I request public records from New Hampshire?", "output": "What are the legal processes for obtaining public records in New Hampshire?"},
    ]
    example_prompt = ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")])
    few_shot_prompt = FewShotChatMessagePromptTemplate(example_prompt=example_prompt, examples=examples)
    step_back_prompt = ChatPromptTemplate.from_messages([("system", STEP_BACK_SYSTEM_PROMPT), few_shot_prompt, ("user", "{question}")])

    chain = step_back_prompt | llm | StrOutputParser()
    step_back_question = chain.invoke({"question": original_question})
    logger.info(f"Generated step-back question: '{step_back_question}'")
    return {"step_back_question": step_back_question}
    # Dispatch retrieval for both questions in parallel
    return [Send("retrieval_subgraph", {"retrieval_query": original_question}), Send("retrieval_subgraph", {"retrieval_query": step_back_question, "step_back_question": step_back_question})]  # Pass step_back_question for context in the joiner


def process_original_context_node(state: StepBackState) -> StepBackState:
    """Formats the original context documents into a single string."""
    logger.info("Formatting documents from original retrieval.")
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"origina_context": formatted_string}


def process_step_back_context_node(state: StepBackState) -> StepBackState:
    """Formats the step-back context documents into a single string."""
    logger.info("Formatting documents from step-back retrieval.")
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"step_back_context": formatted_string}


def generate_final_response_node(state: StepBackState) -> AgentState:
    """Generates a final response using both sets of retrieved documents."""
    logger.info("Generating final response using combined context from parallel retrieval.")
    question = state["contextualized_query"]
    normal_context = format_docs(state["origina_context"])
    step_back_context = format_docs(state["step_back_context"])

    response_prompt = ChatPromptTemplate.from_template(STEP_BACK_RESPONSE_PROMPT)
    chain = response_prompt | llm | StrOutputParser()

    final_response = chain.invoke({"question": question, "normal_context": normal_context, "step_back_context": step_back_context})

    return {"final_context": final_response}


workflow = StateGraph(StepBackState)

workflow.add_node("generate_and_dispatch", generate_and_dispatch_node)
workflow.add_node("retrieve_original", retrieval_subgraph)  # The target for the parallel Sends
workflow.add_node("retrieve_step_back", retrieval_subgraph)  # The target for the parallel Sends
workflow.add_node("process_original_context", process_original_context_node)  # Optional formatting step for original context
workflow.add_node("process_step_back_context", process_step_back_context_node)  # Optional formatting
workflow.add_node("generate_final_response", generate_final_response_node)

workflow.set_entry_point("generate_and_dispatch")


def route_form_generate_and_dispatch(state: StepBackState) -> RetrievalSubgraphState:
    """Route based on whether we have both retrieval results."""
    return [Send("retrieve_original", {"retrieval_query": state["contextualized_query"]}), Send("retrieve_step_back", {"retrieval_query": state["step_back_question"]})]


workflow.add_conditional_edges("generate_and_dispatch", route_form_generate_and_dispatch)
workflow.add_edge("retrieve_original", "process_original_context")
workflow.add_edge("retrieve_step_back", "process_step_back_context")
workflow.add_edge("process_original_context", "generate_final_response")
workflow.add_edge("process_step_back_context", "generate_final_response")

# After parallel retrieval, join and generate the final response
workflow.add_edge("retrieval_subgraph", "generate_final_response")
workflow.add_edge("generate_final_response", END)

step_back = workflow.compile()
