"""
Hierarchical Multi-Agent System
Properly orchestrates existing agents following the documented architecture.
Uses enhanced agents with proper typing and dependency injection.
Integrates memory management and summarization features from main branch.
"""

import logging
import os
from functools import partial
from typing import Dict, List, Optional, TypedDict, Union

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, CompiledGraph, StateGraph

# Configuration
from src.config.constant import MODEL_NAME

# Import enhanced agents with proper typing (from current branch)
from src.core.agents.contextualizer.query_understanding import QueryUnderstandingAgent
from src.core.agents.summarizer import summarizer_agent
from src.core.agents.supervisor.complexity_analyzer import ComplexityAnalyzer
from src.core.agents.supervisor.generator import GeneratorAgent

# Import validation and other agents
from src.core.agents.supervisor.validation import validation_agent

# Import memory and summarization features (from main branch)
from src.core.agents.tools.context_processor import context_processor_agent
from src.core.agents.tools.memory.memory import MemoryManager
from src.core.agents.workers.react.react_worker import multi_step_reasoning_agent
from src.core.agents.workers.retriever.retrieval import RetrievalAgent

# Import schemas and types
from src.schemas.agent_types import GenerationResult, QueryComplexityResult, QueryUnderstandingResult, RetrievalResult
from src.schemas.enhanced_context_types import DocumentCitation, ExtractedInformation, SessionMemoryEntry
from src.schemas.state import AgentState

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment setup
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "NEFAC_HIERARCHICAL_MULTI_AGENT"

# Initialize LLM models directly
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
fast_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Initialize agents
complexity_analyzer = ComplexityAnalyzer(llm=fast_llm)
query_understanding_agent_instance = QueryUnderstandingAgent()
retrieval_agent_instance = RetrievalAgent()
generator_agent_instance = GeneratorAgent()
memory_manager = MemoryManager()


# Define TypedDicts for node outputs for enhanced type safety
class SupervisorNodeOutput(TypedDict):
    supervisor_decision: str
    query_complexity: float
    error: Optional[str]


class MemoryRetrievalNodeOutput(TypedDict):
    memory_context: str
    retrieved_memories: List[SessionMemoryEntry]
    error: Optional[str]


class HistoryCheckNodeOutput(TypedDict):
    needs_summarization: bool
    history_summary: Optional[str]
    chat_history: Optional[List[BaseMessage]]
    error: Optional[str]


class QueryUnderstandingNodeOutput(TypedDict):
    contextualized_query: Optional[str]
    intent: Optional[str]
    entities: Optional[List[str]]
    structured_query: Optional[str]
    statistical_query: Optional[str]
    error: Optional[str]


class RetrieverWorkerNodeOutput(TypedDict):
    documents: Optional[List[Document]]
    retrieval_metadata: Optional[Dict[str, Union[str, int, float, bool]]]
    extracted_info: Optional[List[ExtractedInformation]]
    summarized_content: Optional[List[Document]]
    citations: Optional[List[DocumentCitation]]
    session_memory: Optional[List[SessionMemoryEntry]]
    error: Optional[str]


class ReActWorkerNodeOutput(TypedDict):
    answer: Optional[str]
    documents: Optional[List[Document]]
    error: Optional[str]


class GeneratorNodeOutput(TypedDict):
    answer: Optional[str]
    confidence_score: Optional[float]
    sources: Optional[List[str]]
    error: Optional[str]


class ValidationNodeOutput(TypedDict):
    validation: Dict[str, Union[bool, str, float, List[str]]]
    error: Optional[str]


def supervisor_node(state: AgentState) -> SupervisorNodeOutput:
    """
    Supervisor node that analyzes query complexity and makes routing decisions.
    Uses the ComplexityAnalyzer with proper typing.
    """
    try:
        # Convert messages to chat history format
        chat_history = []
        for msg in state.messages:
            if hasattr(msg, "content"):
                chat_history.append(msg)

        # Analyze complexity using improved analyzer
        complexity_result: QueryComplexityResult = complexity_analyzer.analyze_complexity(query=state.user_query, chat_history=chat_history)

        if complexity_result.is_success:
            # Determine routing decision based on complexity
            complexity_score = complexity_result.data.complexity_score
            if complexity_score < 0.3:
                decision = "retriever_worker"
            elif complexity_score < 0.7:
                decision = "retriever_worker"  # Enhanced retrieval for medium complexity
            else:
                decision = "react_worker"

            logger.info(f"Supervisor: Query='{state.user_query}' -> Decision='{decision}', Complexity={complexity_score:.2f}")
            logger.debug(f"Supervisor: Detailed complexity reasoning: {complexity_result.data.reasoning}")

            return {"supervisor_decision": decision, "query_complexity": complexity_score}
        else:
            logger.error(f"Complexity analysis failed: {complexity_result.error}")
            return {"supervisor_decision": "retriever_worker", "query_complexity": 0.5, "error": f"Complexity analysis error: {complexity_result.error}"}  # Fallback

    except Exception as e:
        logger.error(f"Supervisor node error: {e}")
        return {"supervisor_decision": "retriever_worker", "query_complexity": 0.5, "error": f"Supervisor error: {str(e)}"}  # Fallback


def memory_retrieval_node(state: AgentState) -> MemoryRetrievalNodeOutput:
    """
    Memory retrieval node that gets relevant past interactions.
    Uses the existing MemoryManager with enhanced typing.
    """
    try:
        # Retrieve relevant memories
        raw_memories = memory_manager.retrieve_memories(query=state.user_query, user_id=state.user_id, limit=5)

        # Convert to structured SessionMemoryEntry objects
        memory_entries: List[SessionMemoryEntry] = []
        for i, memory in enumerate(raw_memories):
            if hasattr(memory, "content"):
                from src.schemas.enhanced_context_types import create_memory_entry

                memory_entry = create_memory_entry(memory_id=getattr(memory, "id", f"mem_{i}"), content=memory.content, user_id=state.user_id, session_id=getattr(state, "session_id", "default"), memory_type="interaction", relevance_score=getattr(memory, "relevance_score", 0.5))
                memory_entries.append(memory_entry)

        # Create memory summary
        memory_summary = ""
        if memory_entries:
            memory_texts = [entry.content for entry in memory_entries[:3]]
            memory_summary = "\n".join(memory_texts)

        logger.info(f"Memory retrieval: Found {len(memory_entries)} relevant memories")
        return {"memory_context": memory_summary, "retrieved_memories": memory_entries}

    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return {"memory_context": "", "retrieved_memories": [], "error": f"Memory error: {str(e)}"}


def check_history_length_node(state: AgentState) -> HistoryCheckNodeOutput:
    """
    Check if chat history needs summarization based on length threshold.
    Integrates the summarization logic from main branch.
    """
    try:
        SUMMARY_THRESHOLD = 10

        if len(state.chat_history) >= SUMMARY_THRESHOLD:
            # Use the summarizer agent from main branch
            summarizer_with_model = partial(summarizer_agent, model=llm)
            summary_result = summarizer_with_model(state)

            if summary_result.get("error"):
                logger.error(f"Summarization failed: {summary_result['error']}")
                return {"needs_summarization": False, "error": summary_result["error"]}

            # Update state with summary
            return {"needs_summarization": True, "history_summary": summary_result.get("history_summary", ""), "chat_history": summary_result.get("chat_history", state.chat_history)}
        else:
            return {"needs_summarization": False}

    except Exception as e:
        logger.error(f"History length check error: {e}")
        return {"needs_summarization": False, "error": f"History check error: {str(e)}"}


def query_understanding_node(state: AgentState) -> QueryUnderstandingNodeOutput:
    """
    Query understanding node using the enhanced QueryUnderstandingAgent.
    """
    try:
        # Use the enhanced query understanding agent
        understanding_result: QueryUnderstandingResult = query_understanding_agent_instance.understand_query(query=state.user_query, chat_history=state.chat_history, memory_context=getattr(state, "memory_context", ""))

        if understanding_result.is_success:
            logger.info(f"Query understanding: Intent='{understanding_result.data.intent}', Entities={understanding_result.data.entities}")
            return {
                "contextualized_query": understanding_result.data.contextualized_query,
                "intent": understanding_result.data.intent,
                "entities": understanding_result.data.entities,
                "structured_query": understanding_result.data.structured_query,
                "statistical_query": understanding_result.data.statistical_query,
            }
        else:
            logger.error(f"Query understanding failed: {understanding_result.error}")
            return {"error": f"Query understanding error: {understanding_result.error}"}

    except Exception as e:
        logger.error(f"Query understanding node error: {e}")
        return {"error": f"Query understanding error: {str(e)}"}


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


def create_enhanced_graph() -> CompiledGraph:
    """
    Creates the enhanced LangGraph workflow that combines hierarchical architecture
    with memory management and summarization features.
    """
    # Create the workflow
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("memory_retrieval", memory_retrieval_node)
    workflow.add_node("check_history_length", check_history_length_node)
    workflow.add_node("query_understanding", query_understanding_node)
    workflow.add_node("retriever_worker", retriever_worker_node)
    workflow.add_node("react_worker", react_worker_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("error", lambda state: {"answer": "I'm sorry, but I encountered an error. Please try again."})

    # Set entry point
    workflow.set_entry_point("memory_retrieval")

    # Add edges
    workflow.add_edge("memory_retrieval", "check_history_length")

    # Conditional routing from check_history_length
    def route_from_history_check(state: AgentState):
        if state.error:
            return "error"
        return "query_understanding"

    workflow.add_conditional_edges("check_history_length", route_from_history_check, {"query_understanding": "query_understanding", "error": "error"})

    workflow.add_edge("query_understanding", "supervisor")

    # Conditional routing from supervisor
    def route_from_supervisor(state: AgentState):
        if state.error:
            return "error"
        decision = getattr(state, "supervisor_decision", "retriever_worker")
        return decision

    workflow.add_conditional_edges("supervisor", route_from_supervisor, {"retriever_worker": "retriever_worker", "react_worker": "react_worker", "error": "error"})

    # Both workers route to generator
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

    workflow.add_conditional_edges("validation", route_from_validation, {END: END, "retriever_worker": "retriever_worker", "error": "error"})

    workflow.add_edge("error", END)

    # Compile with memory
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Create the enhanced application
app = create_enhanced_graph()
