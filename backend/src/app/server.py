from __future__ import annotations

import logging
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from backend.src.config.node_names import (
    COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE,
    CONTEXTUALIZER_NODE,
    INTENT_CLASSIFICATION_NODE,
    MEMORY_SUMMARIZER_NODE,
)
from backend.src.config.settings import Configuration

# Import enhanced agents with proper typing (from current branch)
from backend.src.core.agents.memory.summarizer import summarization_node
from backend.src.core.agents.query_understanding.complexity_analyzer import analyze_complexity_node
from backend.src.core.agents.query_understanding.contextualizer import contextualizer_node
from backend.src.core.agents.query_understanding.intent_classification import intent_classification_node
from backend.src.core.agents.reasoning.react import multi_step_reasoning_agent
from backend.src.core.agents.supervisor.generator import GeneratorAgent
from backend.src.core.agents.supervisor.validation import validation_agent
from backend.src.schemas.core_types import (
    AgentState,
    DocumentCitation,
    ExtractedInformation,
    GenerationResult,
    MemoryEntry,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize default configuration
default_config = Configuration()

# Initialize models using the configuration
llm = init_chat_model(default_config.generator_model)
generator_agent_instance = GeneratorAgent(default_config)


class MemoryRetrievalNodeOutput(TypedDict):
    memory_context: str
    retrieved_memories: list[MemoryEntry]
    error: str | None


class HistoryCheckNodeOutput(TypedDict):
    needs_summarization: bool
    history_summary: str | None
    chat_history: list[BaseMessage] | None
    error: str | None


class RetrieverWorkerNodeOutput(TypedDict):
    documents: list[Document] | None
    retrieval_metadata: dict[str, str | int | float | bool] | None
    extracted_info: list[ExtractedInformation] | None
    summarized_content: list[Document] | None
    citations: list[DocumentCitation] | None
    session_memory: list[MemoryEntry] | None
    error: str | None


class ReActWorkerNodeOutput(TypedDict):
    answer: str | None
    documents: list[Document] | None
    error: str | None


class GeneratorNodeOutput(TypedDict):
    answer: str | None
    confidence_score: float | None
    sources: list[str] | None
    error: str | None


class ValidationNodeOutput(TypedDict):
    validation: dict[str, bool | str | float | list[str]]
    error: str | None


def retriever_worker_node(state: AgentState) -> RetrieverWorkerNodeOutput:
    """
    Retriever worker node using the enhanced RetrievalAgent.
    """
    try:
        # TODO: Implement retrieval logic here
        # For now, return empty results to prevent main_graph blocking
        logger.info("Retriever worker node called - implementation needed")
        return {"documents": [], "retrieval_metadata": {}, "extracted_info": [], "summarized_content": [], "citations": [], "session_memory": [], "error": None}
    except Exception as e:
        logger.error(f"Retriever worker node error: {e}")
        return {"error": f"Retriever error: {str(e)}"}


def react_worker_node_with_config(state: AgentState, config) -> ReActWorkerNodeOutput:
    """
    ReAct worker node for complex multi-step reasoning with dynamic configuration.
    """
    try:
        # Use the multi-step reasoning agent with provided configuration
        reasoning_result = multi_step_reasoning_agent(state, config, max_steps=3)

        if reasoning_result.get("error"):
            logger.error(f"ReAct reasoning failed: {reasoning_result['error']}")
            return {"error": f"ReAct reasoning error: {reasoning_result['error']}"}

        logger.info("ReAct reasoning completed successfully")
        return {"answer": reasoning_result.get("answer"), "documents": reasoning_result.get("documents", [])}

    except Exception as e:
        logger.error(f"ReAct worker node error: {e}")
        return {"error": f"ReAct worker error: {str(e)}"}


def generator_node_with_config(state: AgentState, config) -> GeneratorNodeOutput:
    """
    Generator node using the enhanced GeneratorAgent with dynamic configuration.
    """
    try:
        # Create generator agent with provided configuration
        generator_agent_instance = GeneratorAgent(config)
        generation_result: GenerationResult = generator_agent_instance.generate_answer(state)

        if generation_result.is_success:
            logger.info("Response generation completed successfully")
            return {"answer": generation_result.data.answer, "confidence_score": generation_result.data.confidence_score, "sources": generation_result.data.sources}
        else:
            logger.error(f"Generation failed: {generation_result.error}")
            return {"error": f"Generation error: {generation_result.error}"}

    except Exception as e:
        logger.error(f"Generator node error: {e}")
        return {"error": f"Generator error: {str(e)}"}


def validation_node_with_config(state: AgentState, config) -> ValidationNodeOutput:
    """
    Validation node to check response quality with dynamic configuration.
    """
    try:
        # Use validation agent with provided configuration
        validation_result = validation_agent(state, config)

        if validation_result.get("error"):
            logger.error(f"Validation failed: {validation_result['error']}")
            return {"validation": {"is_valid": True}, "error": validation_result["error"]}  # Default to valid on error

        logger.info(f"Validation completed: {validation_result.get('validation', {})}")
        return {"validation": validation_result.get("validation", {"is_valid": True})}

    except Exception as e:
        logger.error(f"Validation node error: {e}")
        return {"validation": {"is_valid": True}, "error": f"Validation error: {str(e)}"}  # Default to valid on error


def react_worker_node(state: AgentState) -> ReActWorkerNodeOutput:
    """
    ReAct worker node for complex multi-step reasoning.
    """
    try:
        # Use the multi-step reasoning agent with proper configuration
        reasoning_result = multi_step_reasoning_agent(state, default_config, max_steps=3)

        if reasoning_result.get("error"):
            logger.error(f"ReAct reasoning failed: {reasoning_result['error']}")
            return {"error": f"ReAct reasoning error: {reasoning_result['error']}"}

        logger.info("ReAct reasoning completed successfully")
        return {"answer": reasoning_result.get("answer"), "documents": reasoning_result.get("documents", [])}

    except Exception as e:
        logger.error(f"ReAct worker node error: {e}")
        return {"error": f"ReAct worker error: {str(e)}"}


def generator_node(state: AgentState) -> GeneratorNodeOutput:
    """
    Generator node using the enhanced GeneratorAgent.
    """
    try:
        # Use the enhanced generator agent with proper method
        generation_result: GenerationResult = generator_agent_instance.generate_answer(state)

        if generation_result.is_success:
            logger.info("Response generation completed successfully")
            return {"answer": generation_result.data.answer, "confidence_score": generation_result.data.confidence_score, "sources": generation_result.data.sources}
        else:
            logger.error(f"Generation failed: {generation_result.error}")
            return {"error": f"Generation error: {generation_result.error}"}

    except Exception as e:
        logger.error(f"Generator node error: {e}")
        return {"error": f"Generator error: {str(e)}"}


def validation_node(state: AgentState) -> ValidationNodeOutput:
    """
    Validation node to check response quality.
    """
    try:
        # Use validation agent with proper configuration
        validation_result = validation_agent(state, default_config)

        if validation_result.get("error"):
            logger.error(f"Validation failed: {validation_result['error']}")
            return {"validation": {"is_valid": True}, "error": validation_result["error"]}  # Default to valid on error

        logger.info(f"Validation completed: {validation_result.get('validation', {})}")
        return {"validation": validation_result.get("validation", {"is_valid": True})}

    except Exception as e:
        logger.error(f"Validation node error: {e}")
        return {"validation": {"is_valid": True}, "error": f"Validation error: {str(e)}"}  # Default to valid on error


def tool_node(state: AgentState) -> AgentState:
    return state


# Create the main_graph
main_graph = StateGraph(AgentState, config_schema=Configuration)

# Add all nodes with configuration
main_graph.add_node(MEMORY_SUMMARIZER_NODE, summarization_node)
main_graph.add_node(CONTEXTUALIZER_NODE, contextualizer_node)
main_graph.add_node(INTENT_CLASSIFICATION_NODE, intent_classification_node)
main_graph.add_node(COMPLEXITY_ANALYZER_ANALYZE_COMPLEXITY_NODE, analyze_complexity_node)
main_graph.add_node("tool_node", tool_node)
main_graph.add_node("retriever_worker", retriever_worker_node)
main_graph.add_node("react_worker", react_worker_node_with_config)
main_graph.add_node("generator", generator_node_with_config)
main_graph.add_node("validation", validation_node_with_config)
main_graph.add_node("error", lambda state: {"answer": "I'm sorry, but I encountered an error. Please try again."})

# Set entry point
main_graph.set_entry_point("summarization")
main_graph.add_edge("summarization", "contextualize")
main_graph.add_edge("contextualize", "intent_classification")


def route_from_intent_classification(state: AgentState):
    if getattr(state, "error", None):
        return "error"
    intent_result = getattr(state, "intent", None)
    if intent_result == "info":
        return "analyze_complexity"
    elif intent_result == "general":
        return "generator"
    return "generator"  # Default fallback


main_graph.add_conditional_edges("intent_classification", route_from_intent_classification, {"analyze_complexity": "analyze_complexity", "generator": "generator", "error": "error"})


def route_from_complexity_analysis(state: AgentState):
    if getattr(state, "error", None):
        return "error"
    tool_usage_required = getattr(state, "tool_usage_required", False)
    if tool_usage_required:
        return "tool_node"
    return route_from_tool_node(state)


main_graph.add_conditional_edges("analyze_complexity", route_from_complexity_analysis, {"tool_node": "tool_node", "retriever_worker": "retriever_worker", "react_worker": "react_worker", "error": "error"})


def route_from_tool_node(state: AgentState):
    if getattr(state, "error", None):
        return "error"
    reasoning_required = getattr(state, "reasoning_required", False)
    multi_hop_needed = getattr(state, "multi_hop_needed", False)
    if reasoning_required or multi_hop_needed:
        return "react_worker"
    return "retriever_worker"


main_graph.add_conditional_edges("tool_node", route_from_tool_node, {"react_worker": "react_worker", "retriever_worker": "retriever_worker", "error": "error"})

main_graph.add_edge("retriever_worker", "generator")
main_graph.add_edge("react_worker", "generator")
main_graph.add_edge("generator", "validation")


# Conditional routing from validation
def route_from_validation(state: AgentState):
    if getattr(state, "error", None):
        return "error"
    validation_result = getattr(state, "validation", {})
    if validation_result.get("is_valid", True):
        return END
    else:
        # Loop back for refinement if validation fails
        return "retriever_worker"


main_graph.add_conditional_edges("validation", route_from_validation, {END: END, "retriever_worker": "retriever_worker", "error": "error"})

main_graph.add_edge("error", END)
main_graph.compile()
