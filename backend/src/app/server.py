import logging
from functools import partial
from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.src.config.constant import MODEL_NAME
from backend.src.core.agents.contextualizer.query_understanding import QueryUnderstandingAgent
from backend.src.core.agents.memory.summarizer import summarization_node
from backend.src.core.agents.query_understanding.complexity_analyzer import ComplexityAnalyzer, QueryComplexity, analyze_complexity_node
from backend.src.core.agents.query_understanding.contextualizer import contextualizer_node
from backend.src.core.agents.query_understanding.intent_classification import IntentClassification, intent_classification_node
from backend.src.core.agents.supervisor.generator import GeneratorAgent
from backend.src.core.agents.supervisor.validation import validation_agent
from backend.src.core.agents.tools.context_processor import context_processor_agent
from backend.src.core.agents.workers.react.react_worker import multi_step_reasoning_agent
from backend.src.core.agents.workers.retriever.retrieval import RetrievalAgent
from backend.src.schemas.core_types import (
    AgentState,
    DocumentCitation,
    ExtractedInformation,
    GenerationResult,
    MemoryEntry,
    RetrievalResult,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = ChatOpenAI(model=MODEL_NAME, temperature=0)

complexity_analyzer = ComplexityAnalyzer()
query_understanding_agent_instance = QueryUnderstandingAgent()
retrieval_agent_instance = RetrievalAgent()
generator_agent_instance = GeneratorAgent()


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
        # Use the enhanced retrieval agent
        retrieval_result: RetrievalResult = retrieval_agent_instance.retrieve_documents(query=state.contextualized_query or state.user_query, intent=state.intent, entities=state.entities, structured_query=state.structured_query, statistical_query=state.statistical_query)

        if retrieval_result.is_success:
            # Process documents through context processor (from main branch)
            context_state = AgentState(query=state.user_query, chat_history=state.chat_history, history_summary=getattr(state, "history_summary", ""), documents=retrieval_result.data.documents, session_id=getattr(state, "session_id", None))

            processed_context = context_processor_agent(context_state)

            logger.info(f"Retrieval: Found {len(retrieval_result.data.documents)} documents")
            return {
                "documents": retrieval_result.data.documents,
                "retrieval_metadata": retrieval_result.data.metadata,
                "extracted_info": processed_context.get("extracted_info"),
                "summarized_content": processed_context.get("summarized_content"),
                "citations": processed_context.get("citations"),
                "session_memory": processed_context.get("session_memory"),
            }
        else:
            logger.error(f"Retrieval failed: {retrieval_result.error}")
            return {"error": f"Retrieval error: {retrieval_result.error}"}

    except Exception as e:
        logger.error(f"Retriever worker node error: {e}")
        return {"error": f"Retriever worker error: {str(e)}"}


def react_worker_node(state: AgentState) -> ReActWorkerNodeOutput:
    """
    ReAct worker node for complex multi-step reasoning.
    """
    try:
        # Use the multi-step reasoning agent
        reasoning_result = multi_step_reasoning_agent(state, llm, max_steps=3)

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
        # Use the enhanced generator agent
        generation_result: GenerationResult = generator_agent_instance.generate_response(
            query=state.contextualized_query or state.user_query,
            documents=state.documents,
            intent=state.intent,
            extracted_info=getattr(state, "extracted_info", None),
            citations=getattr(state, "citations", None),
            memory_context=getattr(state, "memory_context", ""),
            history_summary=getattr(state, "history_summary", ""),
        )

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
        # Use validation agent with model
        validation_with_model = partial(validation_agent, model=llm)
        validation_result = validation_with_model(state)

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


def create_enhanced_graph():
    """
    Creates the enhanced LangGraph workflow that combines hierarchical architecture
    with memory management and summarization features.
    """
    # Create the workflow
    workflow = StateGraph(AgentState)

    # Add all nodes

    workflow.add_node("summarizataion", summarization_node)
    workflow.add_node("contextualize", contextualizer_node)
    workflow.add_node("intent_classification", intent_classification_node)
    workflow.add_node("analyze_complexity", analyze_complexity_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("retriever_worker", retriever_worker_node)
    workflow.add_node("react_worker", react_worker_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("error", lambda state: {"answer": "I'm sorry, but I encountered an error. Please try again."})

    # Set entry point
    workflow.set_entry_point("summarization")
    workflow.add_edge("summarization", "contextualize")
    workflow.add_edge("contextualize", "intent_classification")

    def route_from_intent_classification(state: IntentClassification):
        if state.error:
            return "error"
        decision = state.intent
        if decision == "info":
            return "analyze_complexity"
        elif decision == "general":
            return "generator"

    workflow.add_conditional_edges("intent_classification", route_from_intent_classification)

    def route_from_complexity_analysis(state: QueryComplexity):
        if state.error:
            return "error"
        if state.tool_usage_required:
            return "tool_node"
        return route_from_tool_node(state)

    workflow.add_conditional_edges("analyze_complexity", route_from_complexity_analysis)

    def route_from_tool_node(state: QueryComplexity):
        if state.error:
            return "error"
        if state.reasoning_required or state.multi_hop_needed:
            return "react_worker"
        return "retriever_worker"

    workflow.add_conditional_edges("tool_node", route_from_tool_node)

    workflow.add_edge("retriever_worker", "generator")
    workflow.add_edge("react_worker", "generator")
    workflow.add_edge("generator", "validation")

    # Conditional routing from validation
    def route_from_validation(state: AgentState):
        if state.error:
            return "error"
        validation_result = getattr(state, "validation", {})
        if validation_result.get("is_valid", True):
            return END
        else:
            # Loop back for refinement if validation fails
            return "retriever_worker"

    workflow.add_conditional_edges("validation", route_from_validation)

    workflow.add_edge("error", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Create the enhanced application
app = create_enhanced_graph()


async def stream_chatbot(user_input: str, thread_id: str, user_id: str = "default_user", session_id: str = None, **kwargs):
    """
    Asynchronous streaming interface to run the chatbot with real-time updates.

    Args:
        user_input: The user's query
        thread_id: Thread identifier for conversation continuity
        user_id: User identifier for memory isolation
        session_id: Session identifier
        **kwargs: Additional configuration parameters

    Yields:
        Event dictionaries containing streaming updates
    """
    try:
        # Create initial state
        initial_state = AgentState(user_query=user_input, user_id=user_id, session_id=session_id or thread_id, thread_id=thread_id, messages=[], chat_history=[])

        # Stream events from the graph
        config = {"configurable": {"thread_id": thread_id}}

        async for event in app.astream_events(initial_state, config=config, version="v1"):
            # Yield the event for processing by the main.py streaming handler
            yield event

    except Exception as e:
        logger.error(f"Error in stream_chatbot: {e}")
        # Yield error event
        yield {"event": "on_chain_end", "name": "error", "data": {"output": {"final_answer": f"I apologize, but I encountered an error: {str(e)}", "error": str(e)}}}
