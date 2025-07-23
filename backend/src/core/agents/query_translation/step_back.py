from typing import List

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langgraph.graph import END, Send, StateGraph
from langgraph.types import RunnableConfig

from src.config.node_names import (
    STEP_BACK_GENERATE_AND_DISPATCH,
    STEP_BACK_GENERATE_FINAL_RESPONSE,
    STEP_BACK_PROCESS_ORIGINAL_CONTEXT,
    STEP_BACK_PROCESS_STEP_BACK_CONTEXT,
    STEP_BACK_RETRIEVE_ORIGINAL,
    STEP_BACK_RETRIEVE_STEP_BACK,
)
from src.config.settings import Configuration
from src.core.agents.retrieval.subgraph import RetrievalSubgraphState, retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState


# --- Subgraph State ---
class StepBackState(QueryTransformerState):
    """State for the step-back query transformation subgraph."""

    step_back_question: str = ""
    original_context: List[Document] = []
    step_back_context: List[Document] = []


# --- Nodes ---
def generate_and_dispatch_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Generates a step-back question and dispatches retrieval for both questions in parallel."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.step_back_generate_model)

    original_question = state["transformed_query"]

    examples = [
        {"input": "Can I film police during a protest in Massachusetts?", "output": "What are the legal rights around recording public officials in Massachusetts?"},
        {"input": "How do I request public records from New Hampshire?", "output": "What are the legal processes for obtaining public records in New Hampshire?"},
    ]
    example_prompt = ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")])
    few_shot_prompt = FewShotChatMessagePromptTemplate(example_prompt=example_prompt, examples=examples)
    step_back_prompt = ChatPromptTemplate.from_messages([("system", configuration.step_back_generate_prompt), few_shot_prompt, ("user", "{question}")])

    chain = step_back_prompt | llm | StrOutputParser()
    step_back_question = chain.invoke({"question": original_question})
    return {"step_back_question": step_back_question}


def process_original_context_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Formats the original context documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"original_context": formatted_string}


def process_step_back_context_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Formats the step-back context documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"step_back_context": formatted_string}


def generate_final_response_node(state: StepBackState, config: RunnableConfig) -> QueryTransformerState:
    """Generates a final response using both sets of retrieved documents."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_chat_model(configuration.step_back_response_model)

    question = state["transformed_query"]
    normal_context = state["original_context"]
    step_back_context = state["step_back_context"]

    response_prompt = ChatPromptTemplate.from_template(configuration.step_back_response_prompt)
    chain = response_prompt | llm | StrOutputParser()

    final_response = chain.invoke({"question": question, "normal_context": normal_context, "step_back_context": step_back_context})

    return {"transformed_context": final_response}


workflow = StateGraph(StepBackState)

workflow.add_node(STEP_BACK_GENERATE_AND_DISPATCH, generate_and_dispatch_node)
workflow.add_node(STEP_BACK_RETRIEVE_ORIGINAL, retrieval_subgraph)  # The target for the parallel Sends
workflow.add_node(STEP_BACK_RETRIEVE_STEP_BACK, retrieval_subgraph)  # The target for the parallel Sends
workflow.add_node(STEP_BACK_PROCESS_ORIGINAL_CONTEXT, process_original_context_node)  # Optional formatting step for original context
workflow.add_node(STEP_BACK_PROCESS_STEP_BACK_CONTEXT, process_step_back_context_node)  # Optional formatting
workflow.add_node(STEP_BACK_GENERATE_FINAL_RESPONSE, generate_final_response_node)

workflow.set_entry_point(STEP_BACK_GENERATE_AND_DISPATCH)


def route_form_generate_and_dispatch(state: StepBackState) -> RetrievalSubgraphState:
    """Route based on whether we have both retrieval results."""
    return [Send(STEP_BACK_RETRIEVE_ORIGINAL, {"retrieval_query": state["transformed_query"]}), Send(STEP_BACK_RETRIEVE_STEP_BACK, {"retrieval_query": state["step_back_question"]})]


workflow.add_conditional_edges(STEP_BACK_GENERATE_AND_DISPATCH, route_form_generate_and_dispatch)
workflow.add_edge(STEP_BACK_RETRIEVE_ORIGINAL, STEP_BACK_PROCESS_ORIGINAL_CONTEXT)
workflow.add_edge(STEP_BACK_RETRIEVE_STEP_BACK, STEP_BACK_PROCESS_STEP_BACK_CONTEXT)
workflow.add_edge(STEP_BACK_PROCESS_ORIGINAL_CONTEXT, STEP_BACK_GENERATE_FINAL_RESPONSE)
workflow.add_edge(STEP_BACK_PROCESS_STEP_BACK_CONTEXT, STEP_BACK_GENERATE_FINAL_RESPONSE)

# After parallel retrieval, join and generate the final response
workflow.add_edge(STEP_BACK_RETRIEVE_STEP_BACK, STEP_BACK_GENERATE_FINAL_RESPONSE)
workflow.add_edge(STEP_BACK_GENERATE_FINAL_RESPONSE, END)

step_back = workflow.compile()
