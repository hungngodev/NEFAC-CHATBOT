from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langgraph.graph import END, StateGraph
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
from src.core.agents.retrieval.subgraph import retrieval_subgraph
from src.core.agents.tools.document_formatter import format_docs
from src.schemas.state import QueryTransformerState
from src.utils.model_factory import init_model


# --- Subgraph State ---
class StepBackState(QueryTransformerState):
    """State for the step-back query transformation subgraph."""

    step_back_question: str = ""
    original_context: list[Document] = []
    step_back_context: list[Document] = []


# --- Nodes ---
async def generate_and_dispatch_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Generates a step-back question and dispatches retrieval for both questions in parallel."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.step_back_generate_model, disable_streaming=configuration.disable_streaming)

    original_question = state["transformed_query"]

    examples = [
        {"input": "Can I film police during a protest in Massachusetts?", "output": "What are the legal rights around recording public officials in Massachusetts?"},
        {"input": "How do I request public records from New Hampshire?", "output": "What are the legal processes for obtaining public records in New Hampshire?"},
    ]
    example_prompt = ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")])
    few_shot_prompt = FewShotChatMessagePromptTemplate(example_prompt=example_prompt, examples=examples)
    step_back_prompt = ChatPromptTemplate.from_messages([("system", configuration.step_back_generate_prompt), few_shot_prompt, ("user", "{question}")])

    chain = step_back_prompt | llm | StrOutputParser()
    step_back_question = await chain.ainvoke({"question": original_question})
    return {"step_back_question": step_back_question, "retrieval_query": step_back_question}


def process_original_context_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Formats the original context documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"original_context": formatted_string, "retrieval_query": state["step_back_question"]}


def process_step_back_context_node(state: StepBackState, config: RunnableConfig) -> StepBackState:
    """Formats the step-back context documents into a single string."""
    documents = state["documents"]
    formatted_string = format_docs(documents)
    return {"step_back_context": formatted_string}


async def generate_final_response_node(state: StepBackState, config: RunnableConfig) -> QueryTransformerState:
    """Generates a final response using both sets of retrieved documents."""
    configuration = Configuration.from_runnable_config(config)
    llm = init_model(configuration.step_back_response_model, disable_streaming=configuration.disable_streaming)

    question = state["transformed_query"]
    normal_context = state["original_context"]
    step_back_context = state["step_back_context"]

    response_prompt = ChatPromptTemplate.from_template(configuration.step_back_response_prompt)
    chain = response_prompt | llm | StrOutputParser()

    final_response = await chain.ainvoke({"question": question, "normal_context": normal_context, "step_back_context": step_back_context})

    return {"transformed_context": final_response}


workflow = StateGraph(StepBackState)

workflow.add_node(
    STEP_BACK_GENERATE_AND_DISPATCH,
    generate_and_dispatch_node,
    metadata={
        "description": "Generates step-back question and dispatches parallel retrieval for both original and step-back queries",
        "dependencies": ["transformed_query"],
        "outputs": ["step_back_question"],
        "strategy": "step_back_prompting",
        "expected_duration": "2-4s",
        "model_type": "step_back_generate_model",
        "parallel_dispatch": True,
    },
)

workflow.add_node(
    STEP_BACK_RETRIEVE_ORIGINAL,
    retrieval_subgraph,
    metadata={
        "description": "Retrieval subgraph for original query in step-back strategy",
        "dependencies": ["transformed_query"],
        "outputs": ["documents"],
        "strategy": "multi_strategy_retrieval",
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "context": "original_question",
    },
)

workflow.add_node(
    STEP_BACK_RETRIEVE_STEP_BACK,
    retrieval_subgraph,
    metadata={
        "description": "Retrieval subgraph for step-back query in step-back strategy",
        "dependencies": ["step_back_question"],
        "outputs": ["documents"],
        "strategy": "multi_strategy_retrieval",
        "expected_duration": "3-8s",
        "retrieval_methods": ["vector", "hybrid", "knowledge_graph"],
        "context": "step_back_question",
    },
)

workflow.add_node(
    STEP_BACK_PROCESS_ORIGINAL_CONTEXT,
    process_original_context_node,
    metadata={"description": "Formats original context documents from retrieval into string", "dependencies": ["documents"], "outputs": ["original_context"], "strategy": "document_formatting", "expected_duration": "0.5-1s", "formatter": "format_docs", "context_type": "original"},
)

workflow.add_node(
    STEP_BACK_PROCESS_STEP_BACK_CONTEXT,
    process_step_back_context_node,
    metadata={"description": "Formats step-back context documents from retrieval into string", "dependencies": ["documents"], "outputs": ["step_back_context"], "strategy": "document_formatting", "expected_duration": "0.5-1s", "formatter": "format_docs", "context_type": "step_back"},
)

workflow.add_node(
    STEP_BACK_GENERATE_FINAL_RESPONSE,
    generate_final_response_node,
    metadata={
        "description": "Generates final response by combining original and step-back contexts",
        "dependencies": ["original_context", "step_back_context", "transformed_query"],
        "outputs": ["transformed_context"],
        "strategy": "dual_context_synthesis",
        "expected_duration": "3-6s",
        "model_type": "step_back_response_model",
        "synthesis_method": "dual_context_integration",
    },
)

workflow.set_entry_point(STEP_BACK_GENERATE_AND_DISPATCH)
workflow.add_edge(STEP_BACK_GENERATE_AND_DISPATCH, STEP_BACK_RETRIEVE_ORIGINAL)
workflow.add_edge(STEP_BACK_RETRIEVE_ORIGINAL, STEP_BACK_PROCESS_ORIGINAL_CONTEXT)
workflow.add_edge(STEP_BACK_PROCESS_ORIGINAL_CONTEXT, STEP_BACK_RETRIEVE_STEP_BACK)
workflow.add_edge(STEP_BACK_RETRIEVE_STEP_BACK, STEP_BACK_PROCESS_STEP_BACK_CONTEXT)
workflow.add_edge(STEP_BACK_PROCESS_STEP_BACK_CONTEXT, STEP_BACK_GENERATE_FINAL_RESPONSE)
workflow.add_edge(STEP_BACK_GENERATE_FINAL_RESPONSE, END)

step_back = workflow.compile(
    debug=True,
    name="step_back_strategy_parallel",
)
